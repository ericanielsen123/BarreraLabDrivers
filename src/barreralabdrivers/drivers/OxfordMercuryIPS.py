"""
QCoDeS driver for the Oxford Mercury iPS
written by Eames Donovan
July 21 2025 revision 0.1: basic identification and read functionality
"""

import qcodes.validators as vals
import logging

from time import sleep
from typing import Any, Optional
from functools import partial
from qcodes.instrument import InstrumentModule, VisaInstrument
from qcodes.parameters import Parameter
from qcodes.validators import Ints, Numbers
import re
import numpy as np
import time

log = logging.getLogger(__name__)


class iPSMagnet(InstrumentModule):
    def __init__(
        self, parent: "MercuryiPS", name: str, thermometer: str, heater: str
    ) -> None:
        super().__init__(parent, name)

        """
        parent: the parent class which this magnet is attatched to
        name: the name of the magnet (I usually choose mag)
        thermometer: the UID of the magnet thermometer (MB1.T1)
        heater: the UID of the magnet heater which is in a PID loop with the thermometer (MB0.H1)
        """

        """
        status
        get: none -> str
        retrieves the alarms for the magnet
        set:
        not defined
        """

        self.status = self.add_parameter(
            name="status",
            get_cmd=lambda: self._flush_then_get("READ:DEV:GRPZ:PSU:STAT"),
            get_parser=str,
        )

        """
        switch_htr_id
        get: none -> str
        returns the UID of the switch heater attatched to the magnet group
        set:
        not yet defined
        """
        self.switch_htr_id = self.add_parameter(
            name="switch_htr_id",
            get_cmd=lambda: self._flush_then_get("READ:DEV:GRPZ:PSU:SWPR"),
            get_parser=str,
        )

        """
        switch_htr
        get: none -> str (ON or OFF)
        returns the ON / OFF status of the switch heater attatched to the magnet group
        set: str ('ON' or 'OFF') -> none
        not yet defined
        """

        self.switch_htr = self.add_parameter(
            name="switch_htr",
            get_cmd=lambda: self._flush_then_get("READ:DEV:GRPZ:PSU:SIG:SWHT"),
            get_parser=str,
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:GRPZ:PSU:SIG:SWHT:{self._safe_swtich(self._on_or_off(val))}"
            ),
        )

        """
        curr
        get: none -> float 
        returns magnet power supply current in amps. Note that in persistent mode, we can set the PS current while the magnet super-current is non-zero
        set:
        not yet defined
        """

        self.curr = self.add_parameter(
            name="curr",
            unit="A",
            get_cmd=lambda: self._flush_then_get("READ:DEV:GRPZ:PSU:SIG:CURR"),
            get_parser=self._parse_response_to_float,
        )

        """
        fset
        get: none -> str
        returns the current magnetic field setpoint in Tesla
        set: float -> none 
        adjusts the field setpoint in Tesla
        """
        self.fset = self.add_parameter(
            name="fset",
            unit="T",
            get_cmd=lambda: self._flush_then_get("READ:DEV:GRPZ:PSU:SIG:FSET"),
            get_parser=self._parse_response_to_float,
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:GRPZ:PSU:SIG:FSET:{val}"
            ),
            vals=Numbers(-12, 12),
        )

        """
        supply_field
        get: none -> float
        returns the field that the PS is trying to supply in Tesla
        """

        self.supply_field = self.add_parameter(
            name="supply_field",
            unit="T",
            get_cmd=lambda: self._flush_then_get("READ:DEV:GRPZ:PSU:SIG:FLD"),
            get_parser=self._parse_response_to_float,
        )

        """
        field:
        get: none -> float
        returns the current magnetic field in Tesla
        set: val -> none
        Uses ips.mag.fset(val), followed by ips.mag.rampmode('to_set'). 
        Can only be used when ips.mag.switch_htr is 'ON' 
        """
        self.field = self.add_parameter(
            name="field",
            unit="T",
            get_cmd=lambda: self._flush_then_get("READ:DEV:GRPZ:PSU:SIG:PFLD"),
            get_parser=self._parse_response_to_float,
            set_cmd=lambda val: self._set_field(val),
        )

        """
        
        rampmode:
        get: none -> str
        returns the current magnetic field ramp status 
        set: str : (hold, to_set, zero, clamp) -> none 
        adjusts the ramp mode of the iPS
        """
        self.rampmode = self.add_parameter(
            name="rampmode",
            get_cmd=lambda: self._flush_then_get("READ:DEV:GRPZ:PSU:ACTN"),
            get_parser=str,
            set_cmd=lambda cmd: self._set_with_flush(
                f"SET:DEV:GRPZ:PSU:ACTN:{self._ramp_action(cmd)}"
            ),
            vals=vals.Enum("HOLD", "TO_SET", "ZERO", "CLAMP"),
        )

        """
        rateset:
        get: none -> float
        returns the target ramprate of the magnet in T/min
        set: float -> none
        sets the target ramprate of the magnet in T/min
        """

        self.rateset = self.add_parameter(
            name="rateset",
            unit="T/min",
            get_cmd=lambda: self._flush_then_get("READ:DEV:GRPZ:PSU:SIG:RFST"),
            get_parser=self._parse_response_to_float,
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:GRPZ:PSU:SIG:RFST:{val}"
            ),
            vals=Numbers(0, 0.3),
        )

        """
        ramprate:
        get: none -> float
        returns the current ramprate of the magnet in T/min
        set: 
        not defined
        """
        self.ramprate = self.add_parameter(
            name="ramprate",
            unit="T/min",
            get_cmd=lambda: self._flush_then_get("READ:DEV:GRPZ:PSU:SIG:RFLD"),
            get_parser=self._parse_response_to_float,
        )

        self.thermometer = thermometer
        self.heater = heater

        self.temp = self.add_parameter(
            name="temp",
            label=f"Temperature of {self.full_name}",
            unit="K",
            get_cmd=lambda: self._flush_then_get(
                f"READ:DEV:{self.thermometer}:TEMP:SIG:TEMP"
            ),
            get_parser=self._parse_response_to_float,
        )
        """
        temp
        get: none -> float
        queries the temperature of the thermometer, returns float in Kelvin
        set:
        not yet defined
        """

        self.htr_resistance = self.add_parameter(
            name="htr_resistance",
            unit="ohms",
            label=f"heater Resistance of {self.full_name}",
            get_cmd=lambda: self._flush_then_get(f"READ:DEV:{self.heater}:HTR:RES"),
            # get_parser=self._parse_response_to_float,
        )
        """
        htr_resistance
        get: none -> float
        queries the resistance of the heater, returns float
        set:
        not defined
        """

        self.htr_vlim = self.add_parameter(
            name="htr_vlim",
            unit="V",
            label=f"heater Voltage Limit of {self.full_name}",
            get_cmd=lambda: self._flush_then_get(f"READ:DEV:{self.heater}:HTR:VLIM"),
            # get_parser=self._parse_response_to_float,
        )

        """
        htr_vlim
        get: none -> float
        queries the voltage limit of the heater, returns float
        set:
        not defined
        """

        self.heatpower = self.add_parameter(
            name="heatpower",
            label=f"Heater Power of {self.full_name}",
            unit="W",
            get_cmd=lambda: self._flush_then_get(
                f"READ:DEV:{self.heater}:HTR:SIG:POWR"
            ),
            get_parser=self._parse_response_to_float,
            # set_cmd=lambda pow: self._set_with_flush(
            #     f"SET:DEV:{self.heater}:HTR:SIG:VOLT:{self._power_to_volts(pow)}"
            # ),
            # vals=vals.Numbers(0, self.htr_vlim() ** 2 / self.htr_resistance()),
        )

        """
        heatpower
        get: none -> float
        queries the power of the heater, returns float in Watts
        set: float -> none
        sets the power of the heater, in Watts

        """

        self.tloop_p = self.add_parameter(
            name="tloop_p",
            label=f"Temperature Loop P of {self.full_name}",
            get_cmd=lambda: self._flush_then_get(
                f"READ:DEV:{self.thermometer}:TEMP:LOOP:P"
            ),
            get_parser=self._parse_response_to_float,
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:{self.thermometer}:TEMP:LOOP:P:{val}"
            ),
        )
        """
        tloop_p
        get: none -> float
        queries the P value of the temperature loop, returns float
        set: float -> none
        sets the P value of the temperature loop
        """

        self.tloop_i = self.add_parameter(
            name="tloop_i",
            label=f"Temperature Loop I of {self.full_name}",
            get_cmd=lambda: self._flush_then_get(
                f"READ:DEV:{self.thermometer}:TEMP:LOOP:I"
            ),
            get_parser=self._parse_response_to_float,
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:{self.thermometer}:TEMP:LOOP:I:{val}"
            ),
        )
        """
        tloop_i
        get: none -> float
        queries the I value of the temperature loop, returns float
        set: float -> none
        sets the I value of the temperature loop
        """

        self.tloop_d = self.add_parameter(
            name="tloop_d",
            label=f"Temperature Loop D of {self.full_name}",
            get_cmd=lambda: self._flush_then_get(
                f"READ:DEV:{self.thermometer}:TEMP:LOOP:D"
            ),
            get_parser=self._parse_response_to_float,
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:{self.thermometer}:TEMP:LOOP:D:{val}"
            ),
        )
        """
        tloop_d
        get: none -> float
        queries the D value of the temperature loop, returns float
        set: float -> none
        sets the D value of the temperature loop
        """

        self.tset = self.add_parameter(
            name="tset",
            label=f"Temperature Setpoint of {self.full_name}",
            unit="K",
            get_cmd=lambda: self._flush_then_get(
                f"READ:DEV:{self.thermometer}:TEMP:LOOP:TSET"
            ),
            get_parser=self._parse_response_to_float,
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:{self.thermometer}:TEMP:LOOP:TSET:{val}"
            ),
            vals=vals.Numbers(0, 300),
        )
        """
        tset
        get: none -> float
        queries the temperature PID setpoint of the thermometer, returns float in Kelvin
        set: float (0,300) -> none
        sets the temperature PID setpoint of the thermometer
        """

        self.tloop_mode = self.add_parameter(
            name="tloop_mode",
            label=f"Temperature Loop Mode of {self.full_name}",
            get_cmd=lambda: self._flush_then_get(
                f"READ:DEV:{self.thermometer}:TEMP:LOOP:ENAB"
            ),
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:{self.thermometer}:TEMP:LOOP:ENAB:{self._on_or_off(val)}"
            ),
        )

        """
        tloop_mode
        get: none -> str ("ON" or "OFF")
        queries the temperature loop mode of the thermometer, returns string 
        set: str ("ON" or "OFF") -> none
        sets the temperature loop mode of the thermometer
        """

        self.temp_ramprate = self.add_parameter(
            name="temp_ramprate",
            label=f"Temperature Ramp Rate of {self.full_name}",
            unit="K/min",
            get_cmd=lambda: self._flush_then_get(
                f"READ:DEV:{self.thermometer}:TEMP:LOOP:RSET"
            ),
            get_parser=self._parse_response_to_float,
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:{self.thermometer}:TEMP:LOOP:RSET:{val}"
            ),
        )
        """
        temp_ramprate
        get: none -> float
        queries the temperature ramp rate of the thermometer, returns float
        set: float -> none
        sets the temperature ramp rate of the thermometer
        """

        self.temp_rampmode = self.add_parameter(
            name="temp_rampmode",
            label=f"Temperature Ramp Mode of {self.full_name}",
            get_cmd=lambda: self._flush_then_get(
                f"READ:DEV:{self.thermometer}:TEMP:LOOP:RENA"
            ),
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:{self.thermometer}:TEMP:LOOP:RENA:{self._on_or_off(val)}"
            ),
        )

    def _on_or_off(self, val: str) -> str:
        if val == {} or val is None:
            return None  # Ignore or handle empty case as needed
        val = str(val).strip().upper()
        if val in {"ON", "OFF"}:
            return val
        raise ValueError(f"Expected 'ON' or 'OFF', got {val}")

    def _set_with_flush(self, cmd: str) -> None:
        # The iTC sends a response with every SET cmd, but we don't need it. This flushes the response buffer so we stay up to date with responses
        self.write(cmd)
        try:
            _ = self.root_instrument.visa_handle.read()
        except:
            pass

    def _flush_then_get(self, cmd: str) -> str:
        try:
            _ = self.root_instrument.visa_handle.read()
        except Exception:
            pass  # Likely means buffer was already empty
        return self.root_instrument.visa_handle.query(cmd)

    def _parse_response_to_float(self, response: str) -> float:
        """
        Extracts the last floating point number from a string.
        """

        matches = re.findall(r"[-+]?\d*\.\d+|\d+", response)
        if matches:
            return float(matches[-1])  # Take the last match
        else:
            raise ValueError(f"No numeric value found in response: {response}")

    def _ramp_action(self, cmd: str) -> None:
        if cmd == "HOLD":
            return "HOLD"
        elif cmd == "TO_SET":
            return "RTOS"
        elif cmd == "ZERO":
            return "RTOZ"
        elif cmd == "CLAMP":
            return "CLMP"
        else:
            raise ValueError(f"Expected 'HOLD', 'TO_SET', 'ZERO' or 'CLAMP', got {cmd}")

    def _safe_fset(self, val: float) -> float:
        # If the heater is on, we are in driven mode and there is no mismatch between the magnet field and supply field.
        if self.switch_htr() == "STAT:DEV:GRPZ:PSU:SIG:SWHT:ON":
            return val

        elif self.switch_htr() == "STAT:DEV:GRPZ:PSU:SIG:SWHT:OFF":
            persistent_field = self.field()

            if val == persistent_field:
                return val

            elif val == 0:
                return val

            else:
                print(
                    f"WARNING. The field setpoint {val} T does not equal the persistent field of {persistent_field} T"
                )
                return val

    def _set_field(self, val: float) -> None:
        if self.switch_htr() == "STAT:DEV:GRPZ:PSU:SIG:SWHT:OFF":
            raise ValueError("The heater must be on to set the field")
        if self.switch_htr() == "STAT:DEV:GRPZ:PSU:SIG:SWHT:ON":
            # Using the safe fset method to set the field
            time.sleep(0.2)
            self.fset(self._safe_fset(val))
            time.sleep(1)
            self.rampmode("HOLD")
            time.sleep(1)
            self.rampmode("TO_SET")
            while np.abs(self.field() - val) > 0.002:
                time.sleep(1)

    def _safe_swtich(self, cmd: str) -> str:
        if cmd == "OFF":
            return "OFF"
        elif cmd == "ON":
            persistent_field = self.field()
            supply_field = self.supply_field()
            if (
                np.abs(persistent_field - supply_field) < 0.001
            ):  # Supply field must be within 0.001 T of the persistent field
                return "ON"
            else:
                print(
                    f"WARNING. Persistent field : {persistent_field}T does not equal the supply field : {supply_field}T"
                )
                print("The heater will remain off")
                return "OFF"


class MercuryiPS(VisaInstrument):
    def __init__(
        self, name: str, address: str, terminator: str = "\n", **kwargs: Any
    ) -> None:
        super().__init__(name, address, terminator=terminator, **kwargs)

        self.connect_message()
        self.visa_handle.timeout = 400

        self.add_submodule(
            name="mag",
            submodule=iPSMagnet(
                parent=self, name="mag", thermometer="MB1.T1", heater="MB0.H1"
            ),
        )

        """
        Identification of the powersupply 
        """
        self.add_parameter(
            name="get_identity",
            get_cmd=lambda: self._flush_then_get(f"*IDN?"),
            get_parser=str,
        )

        """
        alarms
        get: none -> str
        returns a string which displays all alarms from the iPS. 
        set:    
        not defined
        """
        self.add_parameter(
            name="alarms",
            get_cmd=lambda: self._flush_then_get("READ:SYS:ALRM"),
            get_parser=str,
        )

        """
        system_status 
        get: none -> str
        returns a string which contains all the instruments attatched to the iTC along with their function. 
        set:
        not defined
        """

        self.add_parameter(
            name="system_status",
            get_cmd=lambda: self._flush_then_get("READ:SYS:CAT"),
            get_parser=str,
        )

    def _parse_response_to_float(self, response: str) -> float:
        """
        Extracts the last floating point number from a string.
        """

        matches = re.findall(r"[-+]?\d*\.\d+|\d+", response)
        if matches:
            return float(matches[-1])  # Take the last match
        else:
            raise ValueError(f"No numeric value found in response: {response}")

    def _set_with_flush(self, cmd: str) -> None:
        # The iTC sends a response with every SET cmd, but we don't need it. This flushes the response buffer so we stay up to date with responses
        self.write(cmd)
        try:
            _ = self.root_instrument.visa_handle.read()
        except:
            pass

    def _flush_then_get(self, cmd: str) -> str:
        try:
            _ = self.root_instrument.visa_handle.read()
        except Exception:
            pass  # Likely means buffer was already empty
        return self.root_instrument.visa_handle.query(cmd)

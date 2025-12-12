"""
QCoDeS driver for the Oxford Mercury iTC
written by Eames Donovan

July 25 2025 revision 0.4: fixing issues with buffering of previous set_cmd's.
                           Pressure on vti has an undiagnosed problem.
                           Direct htr power control not implemented (unknown heater reistance)
July 24 2025 revision 0.3: adding module functionality, which changes "itc.vti_probe_temp"  TO   "itc.vti.temp" , etc. Added pressure control in .vti submodule
July 21 2025 revision 0.2: adding probe temperature PID control + debugging
July 18 2025 revision 0.1: adding basic read functionality for VTI pressure, VTI + probe temp, VTI + probe heater power, and needle valve position

"""

import qcodes.validators as vals
import logging

from typing import Any
from qcodes.instrument import InstrumentModule, VisaInstrument
import re
from numpy import sqrt

log = logging.getLogger(__name__)

"""
helper functions
"""


class ITC_temperature_module(InstrumentModule):
    def __init__(
        self, parent: "MercuryiTC", name: str, thermometer: str, heater: str
    ) -> None:
        """
        parent: The MercuryiTC (VisaInstrument)instance which the module is attatched to
        name: The 'colloquial' name of the module (vti or probe)
        thermometer; the UID of the thermometer which is attatched to the module
        heater: the UID of the heater which is attatched to the module
        """

        super().__init__(parent, name)

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
            get_parser=self._parse_response_to_float,
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
            get_parser=self._parse_response_to_float,
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

        self.ramprate = self.add_parameter(
            name="ramprate",
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
        ramprate
        get: none -> float
        queries the temperature ramp rate of the thermometer, returns float
        set: float -> none
        sets the temperature ramp rate of the thermometer
        """

        self.rampmode = self.add_parameter(
            name="rampmode",
            label=f"Temperature Ramp Mode of {self.full_name}",
            get_cmd=lambda: self._flush_then_get(
                f"READ:DEV:{self.thermometer}:TEMP:LOOP:RENA"
            ),
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:{self.thermometer}:TEMP:LOOP:RENA:{self._on_or_off(val)}"
            ),
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

    def _on_or_off(self, val: str) -> str:
        if val == {} or val is None:
            return None  # Ignore or handle empty case as needed
        val = str(val).strip().upper()
        if val in {"ON", "OFF"}:
            return val
        raise ValueError(f"Expected 'ON' or 'OFF', got {val}")

    def _power_to_volts(self, power: float) -> float:
        # You can only set the voltage applied to a heater, not the power. This function converts from power to voltage
        volt_squared = power * self.htr_resistance()
        volt = sqrt(volt_squared)
        if volt < self.htr_vlim():
            return volt
        else:
            raise ValueError(
                f"Power {power} W exceeds the maximum voltage {self.htr_vlim()} V"
            )

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


class MercuryiTC(VisaInstrument):
    def __init__(
        self, name: str, address: str, terminator: str = "\n", **kwargs: Any
    ) -> None:
        super().__init__(name, address, terminator=terminator, **kwargs)

        self.visa_handle.timeout = 400
        self.connect_message()
        self._set_with_flush("SET:DEV:DB5.P1:PRES:LOOP:AUX:DB4.G1")
        self._set_with_flush("SET:DEV:DB5.P1:PRES:LOOP:SWMD:OFF")
        self._set_with_flush("SET:DEV:DB5.P1:PRES:LOOP:FAUT:OFF")

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
        returns a string which displays all alarms from the iTC. 
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

        # Adding the VTI and probe temperature control modules defined in ITC_temperature_module
        self.add_submodule(
            name="probe",
            submodule=ITC_temperature_module(
                parent=self, name="probe", thermometer="DB8.T1", heater="DB3.H1"
            ),
        )

        self.add_submodule(
            name="vti",
            submodule=ITC_temperature_module(
                parent=self, name="vti", thermometer="MB1.T1", heater="MB0.H1"
            ),
        )

        # Adding VTI pressure params, which are unique to the VTI and not the probe

        """
        pressure
        get: none -> float
        queries the temperature of the VTI circuit, returns float in mBar

        set:
        not yet defined
        """
        self.vti.pressure = self.vti.add_parameter(
            name="pressure",
            label="VTI Pressure",
            unit="mBar",
            get_cmd=lambda: self._flush_then_get("READ:DEV:DB5.P1:PRES:SIG:PRES"),
            get_parser=self._parse_response_to_float,
        )

        """
        nv_percent
        get: none -> float
        queries the percentage open of the needle valve, returns percentage

        set:
        not yet defined
        """
        self.vti.nv_percent = self.vti.add_parameter(
            name="nv_percent",
            label="Needle Valve Percentage",
            unit="%",
            get_cmd=lambda: self._flush_then_get("READ:DEV:DB4.G1:AUX:SIG:PERC"),
            get_parser=self._parse_response_to_float,
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:DB5.P1:PRES:LOOP:FSET:{val}"
            ),
            vals=vals.Numbers(0, 100),
        )

        """
        ploop_aux
        get: none -> str
        returns the device for PID control of the ploop

        set: str (UID) -> none
        sets the device for PID control of the ploop
        """

        self.vti.ploop_aux = self.vti.add_parameter(
            name="ploop_aux",
            label="Pressure Loop Aux",
            get_cmd=lambda: self._flush_then_get("READ:DEV:DB5.P1:PRES:LOOP:AUX"),
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:DB5.P1:PRES:LOOP:AUX:{val}"
            ),
        )

        """
        ploop_htr
        get: none -> str
        returns the heater for PID control of the ploop

        set: str (UID) -> none
        sets the heater for PID control of the ploop
        """

        self.vti.ploop_htr = self.vti.add_parameter(
            name="ploop_htr",
            label="Pressure Loop Heater",
            get_cmd=lambda: self._flush_then_get("READ:DEV:DB5.P1:PRES:LOOP:HTR"),
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:DB5.P1:PRES:LOOP:HTR:{val}"
            ),
        )

        """
        ploop_p
        get: none -> float
        gets the pressure loop PID P parameter, returns float

        set: float -> none
        sets the pressure loop PID P parameter
        """
        self.vti.ploop_p = self.vti.add_parameter(
            name="ploop_p",
            label="Pressure Loop PID P",
            get_cmd=lambda: self._flush_then_get("READ:DEV:DB5.P1:PRES:LOOP:P"),
            get_parser=self._parse_response_to_float,
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:DB5.P1:PRES:LOOP:P:{val}"
            ),
        )

        """
        ploop_i
        get: none -> float
        gets the pressure loop PID I parameter, returns float

        set: float -> none
        sets the pressure loop PID I parameter
        """
        self.vti.ploop_i = self.vti.add_parameter(
            name="ploop_i",
            label="Pressure Loop PID I",
            get_cmd=lambda: self._flush_then_get("READ:DEV:DB5.P1:PRES:LOOP:I"),
            get_parser=self._parse_response_to_float,
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:DB5.P1:PRES:LOOP:I:{val}"
            ),
        )

        """
        ploop_d
        get: none -> float
        gets the pressure loop PID D parameter, returns float

        set: float -> none
        sets the pressure loop PID D parameter
        """
        self.vti.ploop_d = self.vti.add_parameter(
            name="ploop_d",
            label="Pressure Loop PID D",
            get_cmd=lambda: self._flush_then_get("READ:DEV:DB5.P1:PRES:LOOP:D"),
            get_parser=self._parse_response_to_float,
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:DB5.P1:PRES:LOOP:D:{val}"
            ),
        )

        """
        ploop_mode
        get: none -> str ("ON" or "OFF")
        gets the pressure loop PID mode, returns string

        set: str ("ON" or "OFF")-> none
        sets the pressure loop PID mode
        """
        self.vti.ploop_mode = self.vti.add_parameter(
            name="ploop_mode",
            label="Pressure Loop PID Mode",
            get_cmd=lambda: self._flush_then_get("READ:DEV:DB5.P1:PRES:LOOP:ENAB"),
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:DB5.P1:PRES:LOOP:ENAB:{self._on_or_off(val)}"
            ),
        )

        """
        pset
        get: none -> float
        gets the pressure setpoint, returns float in mBar

        set: float(0,2000) -> none
        sets the pressure setpoint in mBar
        """

        self.vti.pset = self.vti.add_parameter(
            name="pset",
            label="Pressure Setpoint",
            unit="mBar",
            get_cmd=lambda: self._flush_then_get("READ:DEV:DB5.P1:PRES:LOOP:PSET"),
            # get_parser=self._parse_response_to_float,
            set_cmd=lambda val: self._set_with_flush(
                f"SET:DEV:DB5.P1:PRES:LOOP:PSET:{val}"
            ),
            vals=vals.Numbers(0, 2000),
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

    def _on_or_off(self, val: str) -> str:
        if val == {} or val is None:
            return None  # Ignore or handle empty case as needed
        val = str(val).strip().upper()
        if val in {"ON", "OFF", "ON", "OFF"}:
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

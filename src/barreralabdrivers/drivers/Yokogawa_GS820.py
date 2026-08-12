import logging

from functools import partial
from typing import Any, Literal, Optional, Union

import qcodes.validators as vals
from qcodes.instrument import InstrumentChannel, VisaInstrument
from qcodes.parameters import ( DelegateParameter, create_on_off_val_mapping, Parameter )
from qcodes.validators import Bool, Enum, Ints, Numbers

ModeType = Literal["CURR", "VOLT"]

log = logging.getLogger(__name__)


def _float_round(val: float) -> int:
    """
    Rounds a floating number

    Args:
        val: number to be rounded

    Returns:
        Rounded integer
    """
    return round(float(val))


class YokogawaGS200Exception(Exception):
    pass



class YokogawaGS820Channel(InstrumentChannel): 
    """
    Class to hold the two Yokogawa channels, i.e.
    CHANNEL1 and CHANNEL2.
    """

    def __init__(self, parent: "YokogawaGS820", name: str, channel: str) -> None:
        """
        Args:
            parent: The YokogawaGS820 instance to which the channel is
                to be attached.
            name: The 'colloquial' name of the channel
            channel: The name used by the Yokogawa, i.e. either
                'channel1' or 'channel2'
        """

        if channel not in ["channel1", "channel2"]:
            raise ValueError('channel must be either "channe1" or "channel2"')

        super().__init__(parent, name)
        self.model = self._parent.model
        self._extra_visa_timeout = 5000
        self.channel = channel

        self.vrange = self._parent.vranges[self.model]
        self.irange = self._parent.iranges[self.model]

        self.output = Parameter(
            "output",
            label="Output State",
            get_cmd=self.state,
            set_cmd=lambda x: self.on() if x else self.off(),
            val_mapping=create_on_off_val_mapping(on_val=1, off_val=0), 
            instrument=self
        )
        """Control channel output"""

        self.source_mode = Parameter(
            "source_mode",
            label="Source Mode",
            get_cmd=f"{self.channel}:SOUR:FUNC?",
            set_cmd=self._set_source_mode,
            vals=Enum("VOLT", "CURR"),
            instrument=self
        )
        """Select Source mode (voltage/current)"""

        # We need to get the source_mode value here as we cannot rely on the
        # default value that may have been changed before we connect to the
        # instrument (in a previous session or via the frontpanel).
        
        # self.source_mode()

        self.voltage_range = Parameter(
            "voltage_range",
            label="Voltage Source Range",
            unit="V",
            get_cmd=partial(self._get_range, "VOLT"),
            set_cmd=partial(self._set_range, "VOLT"),
            get_parser=float,
            vals=Enum(*self.vrange),
            snapshot_exclude=self.source_mode() == "CURR",
            instrument=self
        )
        """Parameter Voltage Range"""

        self.current_range = Parameter(
            "current_range",
            label="Current Source Range",
            unit="I",
            get_cmd=partial(self._get_range, "CURR"),
            set_cmd=partial(self._set_range, "CURR"),
            vals=Enum(*self.irange),
            get_parser=float,
            snapshot_exclude=self.source_mode() == "VOLT",
            instrument=self
        )
        """Parameter Current Range"""

        # Delegate parameter to encapsulate output_range depending on mode
        self.add_parameter("range", parameter_class=DelegateParameter, source=None)

        # The instrument does support autorange 
        self.auto_range = Parameter(
            "auto_range",
            label="Auto Range",
            set_cmd=self._set_auto_range,
            get_cmd=f"{self.channel}:SOUR:RANGE:AUTO?",
            # initial_cache_value=False,
            val_mapping=create_on_off_val_mapping(on_val=1, off_val=0),
            instrument=self
        )
        """Toggle auto range mode"""

        self.voltage = Parameter(
            "voltage",
            label="Voltage",
            unit="V",
            set_cmd=partial(self._get_set_output, "VOLT"),
            get_cmd=partial(self._get_set_output, "VOLT"),
            get_parser=float,
            snapshot_exclude=self.source_mode() == "CURR",
            instrument=self
        )
        """Parameter Voltage"""

        self.current = Parameter(
            "current",
            label="Current",
            unit="I",
            set_cmd=partial(self._get_set_output, "CURR"),
            get_cmd=partial(self._get_set_output, "CURR"),
            get_parser=float,
            snapshot_exclude=self.source_mode() == "VOLT",
            instrument=self
        )
        """Parameter Current"""

        # be careful 
        self.add_parameter(
            "output_level", parameter_class=DelegateParameter, source=None
        )

        # We need to pass the source parameter for delegate parameters
        # (range and output_level) here according to the present
        # source_mode.
        if self.source_mode() == "VOLT":
            self.range.source = self.voltage_range
            self.output_level.source = self.voltage
        else:
            self.range.source = self.current_range
            self.output_level.source = self.current

        self.voltage_limit = Parameter(
            "voltage_limit",
            label="Voltage Protection Limit",
            unit="V",
            vals=Ints(1, 30),
            get_cmd=":SOUR:PROT:VOLT?",
            set_cmd=":SOUR:PROT:VOLT {}",
            get_parser=_float_round,
            set_parser=int,
            instrument=self
        )
        """Parameter Voltage Protection limit"""

        self.current_limit = Parameter(
            "current_limit",
            label="Current Protection Limit",
            unit="I",
            vals=Numbers(1e-3, 200e-3),
            get_cmd=":SOUR:PROT:CURR?",
            set_cmd=":SOUR:PROT:CURR {:.3f}",
            get_parser=float,
            set_parser=float,
            instrument=self
        )
        """Parameter Current Protection Limit"""

        # TODO: configure for 820
        self.four_wire = Parameter(
            "four_wire",
            label="Four Wire Sensing",
            get_cmd=":SENS:REM?",
            set_cmd=":SENS:REM {}",
            val_mapping={
                "off": 0,
                "on": 1,
            },
            instrument=self
        )

        # Note: The guard feature can be used to remove common mode noise.
        # Read the manual to see if you would like to use it
        # Parameter(
        #     "guard",
        #     label="Guard Terminal",
        #     get_cmd=":SENS:GUAR?",
        #     set_cmd=":SENS:GUAR {}",
        #     val_mapping={"off": 0, "on": 1},
        # )

        # # Return measured line frequency
        # Parameter(
        #     "line_freq",
        #     label="Line Frequency",
        #     unit="Hz",
        #     get_cmd="SYST:LFR?",
        #     get_parser=int,
        # )

        # Check if monitor is present, and if so enable measurement
        # monitor_present = "/MON" in self.ask("*OPT?")
        # measure = YokogawaGS200Monitor(self, "measure", monitor_present)
        # self.add_submodule("measure", measure)

        # Reset function
        self.add_function("reset", call_cmd="*RST")

        # self.add_submodule("program", YokogawaGS200Program(self, "program"))

        # Parameter(
        #     "BNC_out",
        #     label="BNC trigger out",
        #     get_cmd=":ROUT:BNCO?",
        #     set_cmd=":ROUT:BNCO {}",
        #     vals=Enum("trigger", "output", "ready"),
        #     docstring="Sets or queries the output BNC signal",
        # )

        # Parameter(
        #     "BNC_in",
        #     label="BNC trigger in",
        #     get_cmd=":ROUT:BNCI?",
        #     set_cmd=":ROUT:BNCI {}",
        #     vals=Enum("trigger", "output"),
        #     docstring="Sets or queries the input BNC signal",
        # )

        self.system_errors = Parameter(
            "system_errors",
            get_cmd=":SYSTem:ERRor?",
            docstring="returns the oldest unread error message from the event "
            "log and removes it from the log.",
            instrument=self
        )


    def on(self) -> None:
        """Turn output on"""
        self.write(f"{self.channel}:OUTPUT:STATE 1")
        
    def off(self) -> None:
        """Turn output off"""
        self.write(f"{self.channel}:OUTPUT:STATE 0")

    def state(self) -> int:
        """Check state"""
        state = int(self.ask("OUTPUT:STATE?"))
        return state

    def ramp_voltage(self, ramp_to: float, step: float, delay: float) -> None:
        """
        Ramp the voltage from the current level to the specified output.

        Args:
            ramp_to: The ramp target in Volt
            step: The ramp steps in Volt
            delay: The time between finishing one step and
                starting another in seconds.
        """
        self._assert_mode("VOLT")
        self._ramp_source(ramp_to, step, delay)

    def ramp_current(self, ramp_to: float, step: float, delay: float) -> None:
        """
        Ramp the current from the current level to the specified output.

        Args:
            ramp_to: The ramp target in Ampere
            step: The ramp steps in Ampere
            delay: The time between finishing one step and starting
                another in seconds.
        """
        self._assert_mode("CURR")
        self._ramp_source(ramp_to, step, delay)

    def _ramp_source(self, ramp_to: float, step: float, delay: float) -> None:
        """
        Ramp the output from the current level to the specified output

        Args:
            ramp_to: The ramp target in volts/amps
            step: The ramp steps in volts/ampere
            delay: The time between finishing one step and
                starting another in seconds.
        """
        saved_step = self.output_level.step
        saved_inter_delay = self.output_level.inter_delay

        self.output_level.step = step
        self.output_level.inter_delay = delay
        self.output_level(ramp_to)

        self.output_level.step = saved_step
        self.output_level.inter_delay = saved_inter_delay

    def _get_set_output(
        self, mode: ModeType, output_level: Optional[float] = None
    ) -> Optional[float]:
        """
        Get or set the output level.

        Args:
            mode: "CURR" or "VOLT"
            output_level: If missing, we assume that we are getting the
                current level. Else we are setting it
        """
        if self.source_mode.get_latest() != mode:
            return float(self.ask(f"{self.channel}:MEAS?"))
        else:
            if output_level is not None:
                 self._set_output(output_level)
                 return None
            return float(self.ask(f"{self.channel}:SOUR:{mode}:LEV?"))
    

    def _set_output(self, output_level: float) -> None:
        """
        Set the output of the instrument.

        Args:
            output_level: output level in Volt or Ampere, depending
                on the current mode.
        """
        auto_enabled = self.auto_range()
        mode = self.source_mode.get_latest()
        if not auto_enabled:
            self_range = self.range()
            if self_range is None:
                raise RuntimeError(
                    "Trying to set output but not in auto mode and range is unknown."
                )
        else:
            if mode == "CURR":
                self_range = max(self.vrange)
            else:
                self_range = max(self.vrange)

        # Check we are not trying to set an out of range value
        if self.range() is None or abs(output_level) > abs(self_range):
            # Check that the range hasn't changed
            if not auto_enabled:
                self_range = self.range.get_latest()
                if self_range is None:
                    raise RuntimeError(
                        "Trying to set output but not in"
                        " auto mode and range is unknown."
                    )
            # If we are still out of range, raise a value error
            if abs(output_level) > abs(self_range):
                raise ValueError(
                    "Desired output level not in range"
                    f" [-{self_range:.3}, {self_range:.3}]"
                )

        # if auto_enabled:
        #     auto_str = ":AUTO"
        # else:
        #     auto_str = ""
        # cmd_str = f":SOUR:LEV{auto_str} {output_level:.5e}"
        mode = self.source_mode.get_latest()
        cmd_str = f"{self.channel}:SOUR:{mode}:LEV {output_level:.5e}"
        self.write(cmd_str)

    # def _update_measurement_module(
    #     self,
    #     source_mode: Optional[ModeType] = None,
    #     source_range: Optional[float] = None,
    # ) -> None:
    #     """
    #     Update validators/units as source mode/range changes.

    #     Args:
    #         source_mode: "CURR" or "VOLT"
    #         source_range: New range.
    #     """
    #     if not self.measure.present:
    #         return

    #     if source_mode is None:
    #         source_mode = self.source_mode.get_latest()
    #     # Get source range if auto-range is off
    #     if source_range is None and not self.auto_range():
    #         source_range = self.range()

    #     self.measure.update_measurement_enabled(source_mode, source_range)

    def _set_auto_range(self, val: bool) -> None:
        """
        Enable/disable auto range.

        Args:
            val: auto range on or off
        """
        self._auto_range = val
        # Disable measurement if auto range is on
        # if self.measure.present:
        #     # Disable the measurement module if auto range is enabled,
        #     # because the measurement does not work in the
        #     # 10mV/100mV ranges.
        #     self.measure._enabled &= not val

        self.write(f"{self.channel}:SOUR:RANGE:AUTO {val}")

    def _assert_mode(self, mode: ModeType) -> None:
        """
        Assert that we are in the correct mode to perform an operation.

        Args:
            mode: "CURR" or "VOLT"
        """
        if self.source_mode.get_latest() != mode:
            raise ValueError(
                f"Cannot get/set {mode} settings while in {self.source_mode.get_latest()} mode"
            )

    def _set_source_mode(self, mode: ModeType) -> None:
            """
            Set output mode and change delegate parameters' source accordingly.
            Also, exclude/include the parameters from snapshot depending on the
            mode. The instrument does not support 'current', 'current_range'
            parameters in "VOLT" mode and 'voltage', 'voltage_range' parameters
            in "CURR" mode.
    
            Args:
                mode: "CURR" or "VOLT"
    
            """
            if self.output() == "on":
                raise YokogawaGS200Exception("Cannot switch mode while source is on")
    
            if mode == "VOLT":
                self.range.source = self.voltage_range
                self.output_level.source = self.voltage
                self.voltage_range.snapshot_exclude = False
                self.voltage.snapshot_exclude = False
                self.current_range.snapshot_exclude = True
                self.current.snapshot_exclude = True
            else:
                self.range.source = self.current_range
                self.output_level.source = self.current
                self.voltage_range.snapshot_exclude = True
                self.voltage.snapshot_exclude = True
                self.current_range.snapshot_exclude = False
                self.current.snapshot_exclude = False
    
            self.write(f"{self.channel}:SOUR:FUNC {mode}")
            # We set the cache here since `_update_measurement_module`
            # needs the current value which would otherwise only be set
            # after this method exits
            self.source_mode.cache.set(mode)
            # Update the measurement mode
            # self._update_measurement_module(source_mode=mode)
            if mode == 'CURR':
                self.write(f'{self.channel}:SENS:MODE FIX')
                self.write(f'{self.channel}:SENS:FUNC VOLT')
                print('We got em')
            elif mode == 'VOLT':
                self.write(f'{self.channel}:SENS:MODE FIX')
                self.write(f'{self.channel}:SENS:FUNC CURR')

    def _set_range(self, mode: ModeType, output_range: float) -> None:
        """
        Update range

        Args:
            mode: "CURR" or "VOLT"
            output_range: Range to set. For voltage, we have the ranges [10e-3,
                100e-3, 1e0, 10e0, 30e0]. For current, we have the ranges [1e-3,
                10e-3, 100e-3, 200e-3]. If auto_range = False, then setting the
                output can only happen if the set value is smaller than the
                present range.
        """
        self._assert_mode(mode)
        output_range = float(output_range)
        # self._update_measurement_module(source_mode=mode, source_range=output_range)
        self.write(f"{self.channel}:SOUR:{mode}:RANGE {output_range}")

    def _get_range(self, mode: ModeType) -> float:
        """
        Query the present range.

        Args:
            mode: "CURR" or "VOLT"

        Returns:
            range: For voltage, we have the ranges [10e-3, 100e-3, 1e0, 10e0,
                30e0]. For current, we have the ranges [1e-3, 10e-3, 100e-3,
                200e-3]. If auto_range = False, then setting the output can only
                happen if the set value is smaller than the present range.
        """
        self._assert_mode(mode)
        return float(self.ask(f"{self.channel}:SOUR:{mode}:RANGE?"))



    def reset(self) -> None:
        """
        Reset instrument to factory defaults.
        This resets only the relevant channel.
        """
        self.write(f"{self.channel}.reset()")
        # remember to update all the metadata
        log.debug(f"Reset channel {self.channel}. Updating settings...")
        self.snapshot(update=True)


class YokogawaGS820(VisaInstrument):
    """
    QCoDeS driver for the Yokogawa GS820 Multi Channel Source Measure.

    Args:
      name: What this instrument is called locally.
      address: The GPIB or USB address of this instrument
      kwargs: kwargs to be passed to VisaInstrument class
      terminator: read terminator for reads/writes to the instrument.
    """

    def __init__(
        self, name: str, address: str, terminator: str = "\n", **kwargs: Any
    ) -> None:
        super().__init__(name, address, terminator=terminator, **kwargs)

        model = self.IDN()['model']
        supportedmodels = ["765601", "765602", "765611", "765612"]
        if model not in supportedmodels:
            kmstring = ("{}, " * (len(supportedmodels) - 1)).format(*supportedmodels[:-1])
            kmstring += f"and {supportedmodels[-1]}."
            raise ValueError("Unknown model. Supported models are: " + kmstring)
        
        # Get model number from Identification String
        self.model = model

        self.vranges = {
            "765601": [200e-3, 2e0,7e0,18e0],
            "765602" : [200e-3, 2e0,7e0,18e0],
            "765611" : [200e-3, 2e0,20e0,50e0],
            "765612" : [200e-3, 2e0,20e0,50e0]
        }

        self.iranges = {
            "765601": [200e-9, 2e-6,20e-6,200e-6, 2e-3, 20e-3, 200e-3, 1.2e0, 3.2e0],
            "765602" : [200e-9, 2e-6,20e-6,200e-6, 2e-3, 20e-3, 200e-3, 1.2e0, 3.2e0],
            "765611" : [200e-9, 2e-6,20e-6,200e-6, 2e-3, 20e-3, 200e-3, 600e-3, 1.2e0],
            "765612" : [200e-9, 2e-6,20e-6,200e-6, 2e-3, 20e-3, 200e-3, 600e-3, 1.2e0]
        }

        self.channels: list[YokogawaGS820Channel] = []
        for ch in ['1','2']:
            ch_name = f"channel{ch}"
            channel = YokogawaGS820Channel(self, ch_name, ch_name)
            self.add_submodule(ch_name, channel)
            self.channels.append(channel)

        # display
        self.display_settext = Parameter(
            "display_settext", set_cmd=self._display_settext, vals=vals.Strings(),
            instrument=self
        )

        print("GREAT GOOGLY MOOGLY")
        self.connect_message()

    def _display_settext(self, text: str) -> None:
        self.visa_handle.write(f"SYST:DISP:TEXT \"{text}\"")

    def reset(self) -> None:
        """
        Returns instrument to default settings, cancels all pending commands.
        """
        self.write("*RST")

    


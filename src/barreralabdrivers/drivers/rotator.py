from qcodes.instrument.base import Instrument


class Rotator(Instrument):
    """
    Minimal QCoDeS driver for an Attocube rotator.

    This driver only implements a get command for the
    rotator position.

    Parameters
    ----------
    name : str
        QCoDeS instrument name.

    nanopositioner : NanoPositioner
        Connected Attocube NanoPositioner object.

    axis : int
        Attocube axis number corresponding to this rotator.

    position_scale : float
        Conversion factor from the native Attocube position
        units to degrees.

        For an Attocube rotational axis reporting microdegrees,
        use 1e-6.
    """

    def __init__(
        self,
        name,
        nanopositioner,
        axis,
        position_scale=1e-6,
        **kwargs,
    ):

        super().__init__(
            name,
            **kwargs,
        )

        self._nanopositioner = nanopositioner
        self._axis = axis
        self._position_scale = position_scale

        # --------------------------------------------------------
        # Position parameter
        # --------------------------------------------------------

        self.add_parameter(
            "position",
            label="Position",
            unit="degrees",
            get_cmd=self._get_position,
        )

    def _get_position(self):
        """
        Read the rotator position from the Attocube controller
        and convert it to degrees.
        """

        position = self._nanopositioner.get_position(
            self._axis
        )

        return position * self._position_scale
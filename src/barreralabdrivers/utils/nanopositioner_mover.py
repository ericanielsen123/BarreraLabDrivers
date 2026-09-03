from . import AMC

import time


class NanoPositioner:
    """
    Generic Attocube nanopositioner controller.

    This class provides a basic interface to an Attocube AMC
    controller and its axes.

    The axes are intentionally not assigned specific functions
    (X, Y, rotation, etc.). The user specifies which axis is
    which when creating higher-level drivers.

    Parameters
    ----------
    ip : str
        IP address of the Attocube AMC controller.

    n_axes : int
        Number of axes on the controller.
    """

    def __init__(self, ip: str, n_axes: int):

        self.IP = ip
        self.n_axes = n_axes

        # Connect to AMC device
        self.dev = AMC.Device(self.IP)
        self.dev.connect()

    # ============================================================
    # AXIS ACTIVATION
    # ============================================================

    def initialize_axis(self, axis: int):
        """
        Activate a single axis.

        Parameters
        ----------
        axis : int
            Attocube axis number.
        """

        self.dev.control.setControlOutput(axis, True)

    def deactivate_axis(self, axis: int):
        """
        Deactivate a single axis.

        Parameters
        ----------
        axis : int
            Attocube axis number.
        """

        self.dev.control.setControlOutput(axis, False)

    def initialize_axes(self):
        """
        Activate all configured axes.
        """

        for axis in range(self.n_axes):
            self.initialize_axis(axis)

    def deactivate_axes(self):
        """
        Deactivate all configured axes.
        """

        for axis in range(self.n_axes):
            self.deactivate_axis(axis)

    # ============================================================
    # POSITION
    # ============================================================

    def get_position(self, axis: int):
        """
        Get the position of an Attocube axis.

        Parameters
        ----------
        axis : int
            Attocube axis number.

        Returns
        -------
        float
            Position reported by the Attocube controller in
            its native units.

            For linear axes this is typically nm.

            For rotational axes this is typically microdegrees.
        """

        return self.dev.move.getPosition(axis)

    # ============================================================
    # MOVEMENT
    # ============================================================

    def move_to(self, axis: int, position: float):
        """
        Move one axis to an absolute position.

        Parameters
        ----------
        axis : int
            Attocube axis number.

        position : float
            Target position in the native Attocube units.
        """

        self.dev.move.setControlTargetPosition(
            axis,
            position,
        )

        self.dev.control.setControlMove(
            axis,
            True,
        )

    def move_by(self, axis: int, displacement: float):
        """
        Move one axis by a relative displacement.

        Parameters
        ----------
        axis : int
            Attocube axis number.

        displacement : float
            Displacement in native Attocube units.
        """

        position = self.get_position(axis)

        self.move_to(
            axis,
            position + displacement,
        )

    def wait_until_stopped(
        self,
        axis: int,
        poll_interval: float = 0.1,
    ):
        """
        Wait until an axis reaches its target position.

        Parameters
        ----------
        axis : int
            Attocube axis number.

        poll_interval : float
            Time between status checks in seconds.
        """

        while not self.dev.status.getStatusTargetRange(axis):
            time.sleep(poll_interval)

    def stop_axis(self, axis: int):
        """
        Stop movement on a single axis.

        Parameters
        ----------
        axis : int
            Attocube axis number.
        """

        self.dev.control.setControlMove(
            axis,
            False,
        )

    def stop_all(self):
        """
        Stop movement on all configured axes.
        """

        for axis in range(self.n_axes):
            self.stop_axis(axis)

    # ============================================================
    # CONNECTION
    # ============================================================

    def close_conn(self):
        """
        Close the connection to the Attocube AMC controller.
        """

        return self.dev.close()
from qcodes.instrument_drivers.stanford_research import SR86x
from .virtual_params import BaseVoltageSource

# from qcodes.instrument import Instrument, InstrumentBase
from qcodes.parameters import Parameter
from typing import Tuple
import numpy as np
import time

from barreralabdrivers.drivers import Keithley6500


class Balancer:
    def __init__(
        self,
        control: BaseVoltageSource,  # voltage to the known capacitor
        reference: BaseVoltageSource,  # reference to the lockin
        drive: BaseVoltageSource,  # voltage to the unknown capacitor
        Lockin: SR86x,
        frequency: Parameter,
        integration_time: float = 2,
    ):
        self.vcontrol = control
        self.vref = reference
        self.vdrive = drive
        self.li = Lockin
        self.frequerncy = frequency  # signal frequency
        self.int_time = integration_time  # lockin integration timE

        self.multiplier = 1000.0
        self._balanced = False
        self.Kc = np.zeros(2)
        self.Kr = np.zeros(2)
        self.P = 0
        self.V0x = 0
        self.VOy = 0
        self.drive_voltage = 0

        self.vc = 0
        self.vr = 0

    def excite(self, drive: float, ref: float, freq: float) -> None:
        self.frequerncy(freq)
        self.vdrive.voltage(drive)
        self.vref.voltage(ref)
        self.drive_voltage = drive

    def amps_to_pol(self, vc_amp, vr_amp) -> Tuple[float, float]:
        R = np.sqrt(vc_amp**2 + vr_amp**2)
        theta = np.rad2deg(np.arctan2(vr_amp, -vc_amp))
        return R, theta

    def pol_to_amps(self, voltage, phase) -> Tuple[float, float]:
        X = np.abs(voltage * np.cos(np.deg2rad(phase)))
        Y = np.abs(voltage * np.sin(np.deg2rad(phase)))
        return X, Y

    def update_control(self, vc: float, vy: float) -> None:
        self.vc = vc
        self.vr = vy
        R, theta = self.amps_to_pol(vc, vy)
        self.vcontrol.voltage(R)
        self.vcontrol.phase(theta)

    def balance(self, INIT, DELTA, null: bool = False) -> Tuple[float, float]:
        (dx, dy) = DELTA
        (X1, Y1) = INIT
        (X2, Y2) = (X1, Y1 + dy)
        (X3, Y3) = (X1 + dx, Y1)
        coordinates = [(X1, Y1), (X2, Y2), (X3, Y3)]

        L = np.zeros((3, 2), dtype=float)
        for i in range(len(coordinates)):
            self.update_control(*coordinates[i])
            time.sleep(self.int_time)
            L[i] = self.li.X(), self.li.Y()
        L *= self.multiplier

        # Finding Constants from Ashoori thesis
        self.Kr = (L[1] - L[0]) / dy
        self.Kc = (L[2] - L[0]) / dx
        Kr1, Kr2 = self.Kr
        Kc1, Kc2 = self.Kc
        print(f"Kr1, Kr2 = {Kr1, Kr2}")
        print(f"Kc1, Kc2 = {Kc1, Kc2}")

        A = (Kc1 * Kr2) / (Kc2 * Kr1)
        self.P = (1 - A) ** (-1)
        print(f"P = {self.P}")

        # Kmat = np.reciprocal(np.array([[Kr1, Kr2], [Kc1, Kc2]]))
        # Pmat = np.array([[-1, A], [-1, A]])
        # V0y, V0x = [X1, Y1] + A * (np.multiply(Pmat, Kmat) @ L[0]

        self._balanced = True
        return self.null_voltages(X1, Y1, L[0, 0], L[0, 1], null)

    def null_voltages(
        self, X: float, Y: float, Lx: float, Ly: float, null: bool = False
    ) -> Tuple[float, float]:
        if self._balanced:
            self.V0x = X + self.P / self.Kc[1] * (-Ly + self.Kr[1] / self.Kr[0] * Lx)
            self.V0y = Y + self.P / self.Kr[0] * (-Lx + self.Kc[0] / self.Kc[1] * Ly)
            if null:
                self.update_control(self.V0x, self.V0y)
            return self.V0x, self.V0y
        else:
            raise ValueError("Balancer not yet balanced. Call balance() first.")

    def calculate_conductance(self, C_stand) -> float:
        if self._balanced:
            return (
                2 * np.pi * self.frequerncy() * self.V0y * C_stand / self.drive_voltage
            )

    def calculate_capacitance(self, C_stand) -> float:
        if self._balanced:
            return self.V0x * C_stand / self.drive_voltage

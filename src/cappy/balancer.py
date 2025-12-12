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
        control: BaseVoltageSource,  # voltage to the known capacitor.
        # If tuple, it is assumed that first entry is amplitude and second is phase. If single, assumed it has .voltage and .phase methods
        reference: BaseVoltageSource,  # reference to the lockin
        # Ref to the lockin. If none, it is assumed that the ACDAC is providing signal to REF IN of lockin, and amplitude control is a lockin.amplitude method
        drive: BaseVoltageSource,  # voltage to the unknown capacitor
        # If tuple, it is assumed that first entry is amplitude and second is phase. If single, assumed it has .voltage and .phase methods
        Lockin: SR86x,
        frequency: Parameter,
        integration_time: float = 2,
    ):
        if type(control) == tuple:
            self.vcontrolamp = control[0]
            self.vcontrolphase = control[1]
            self.twoparams = True
        else:
            self.vcontrol = control
            self.twoparams = False

        if reference is not None:
            self.vref = reference
        elif reference is None:
            print("2 channel mode in use")

        if type(drive) == tuple:
            self.vdriveamp = drive[0]
            self.vdrivephase = drive[1]
        else:
            self.vdrive = drive
        self.li = Lockin
        self.frequerncy = frequency  # signal frequency
        self.int_time = integration_time  # lockin integration time

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
        if self.twoparams == False:
            self.vdrive.voltage(drive)
            self.vref.voltage(ref)
        elif self.twoparams == True:
            self.vdriveamp(drive)
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

        if self.twoparams == False:
            self.vcontrol.voltage(R)
            self.vcontrol.phase(theta)

        elif self.twoparams == True:
            self.vcontrolamp(R)
            self.vcontrolphase(theta)

    def balanceconfig(self, INIT, DELTA, null: bool = False, Cstand: float = 1):
        self.delta = DELTA
        self.init = INIT
        self.null = null
        self.Cstand = Cstand

    def balance(self) -> Tuple[float, float]:
        (dx, dy) = self.delta
        (X1, Y1) = self.init
        (X2, Y2) = (X1, Y1 + dy)
        (X3, Y3) = (X1 + dx, Y1)
        coordinates = [(X1, Y1), (X2, Y2), (X3, Y3)]

        L = np.zeros((3, 2), dtype=float)
        for i in range(len(coordinates)):
            self.update_control(*coordinates[i])
            time.sleep(self.int_time)
            L[i] = self.li.X(), self.li.Y()
        if self.twoparams == False:

            L *= self.multiplier

        elif self.twoparams == True:
            pass

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
        return self.null_voltages(X1, Y1, L[0, 0], L[0, 1], self.null)

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

    def calculate_conductance(self, V0x: float = None, V0y: float = None) -> float:
        if V0x is None:
            V0x = self.V0x
        if V0y is None:
            V0y = self.V0y
        if self._balanced:
            return (
                2 * np.pi * self.frequerncy() * V0y * self.Cstand / self.drive_voltage
            )
        else:
            raise ValueError("Balancer not yet balanced. Call balance() first.")

    def calculate_capacitance(self, V0x: float = None, V0y: float = None) -> float:
        if V0x is None:
            V0x = self.V0x
        if V0y is None:
            V0y = self.V0y
        if self._balanced:
            return V0x * self.Cstand / self.drive_voltage
        else:
            raise ValueError("Balancer not yet balanced. Call balance() first.")


class Capacitance:
    def __init__(self, parent: Balancer):
        """
        parent is the Balancer which this Capacitance object belongs to
        """
        self.parent_bal = parent
        self.full_name = "capacitance"

    def capconfig(self, offbal=False, rebal=True):
        self.offbal = offbal
        self.rebal = rebal

    def __call__(self, val=None):
        if val is None and self.offbal == False:
            if self.rebal == True:
                self.parent_bal.balance()
                return self.parent_bal.calculate_capacitance()
            elif self.rebal == False:
                return self.parent_bal.calculate_capacitance()

        if val is None and self.offbal == True:
            if (
                self.parent_bal._balanced == False
                and self.parent_bal.null_voltages == False
            ):
                print("Balncer must be balanced and nulled")
            else:
                V0x = self.parent_bal.V0x
                V0y = self.parent_bal.V0y
                Kr1 = self.parent_bal.Kr[0]
                Kr2 = self.parent_bal.Kr[1]
                Kc1 = self.parent_bal.Kc[0]
                Kc2 = self.parent_bal.Kc[1]
                lockin = self.parent_bal.li
                V0xprime = V0x + (Kr1 * lockin.Y() - Kr2 * lockin.X()) / (
                    Kc1 * Kr2 - Kr1 * Kc2
                )
                V0yprime = V0y + (Kc2 * lockin.X() - Kc1 * lockin.Y()) / (
                    Kc1 * Kr2 - Kr1 * Kc2
                )
                return self.parent_bal.calculate_capacitance(V0xprime, V0yprime)

        elif val is not None:
            print("Capacitance is read-only")
        else:
            print("Capacitance is read-only")


class Conductance:
    def __init__(self, parent: Balancer):
        """
        parent is the Balancer which this Conductane object belongs to
        """
        self.parent_bal = parent
        self.full_name = "conductance"

    def conconfig(self, offbal=False, rebal=True):
        self.offbal = offbal
        self.rebal = rebal

    def __call__(self, val=None):
        if val is None and self.offbal == False:
            if self.rebal == True:
                self.parent_bal.balance()
                return self.parent_bal.calculate_conductance()
            elif self.rebal == False:
                return self.parent_bal.calculate_conductance()

        if val is None and self.offbal == True:
            if (
                self.parent_bal._balanced == False
                and self.parent_bal.null_voltages == False
            ):
                print("Balncer must be balanced and nulled")
            else:
                V0x = self.parent_bal.V0x
                V0y = self.parent_bal.V0y
                Kr1 = self.parent_bal.Kr[0]
                Kr2 = self.parent_bal.Kr[1]
                Kc1 = self.parent_bal.Kc[0]
                Kc2 = self.parent_bal.Kc[1]
                lockin = self.parent_bal.li
                V0xprime = V0x + (Kr1 * lockin.Y() - Kr2 * lockin.X()) / (
                    Kc1 * Kr2 - Kr1 * Kc2
                )
                V0yprime = V0y + (Kc2 * lockin.X() - Kc1 * lockin.Y()) / (
                    Kc1 * Kr2 - Kr1 * Kc2
                )
                return self.parent_bal.calculate_conductance(V0xprime, V0yprime)

        elif val is not None:
            print("Conductance is read-only")
        else:
            print("Conductance is read-only")

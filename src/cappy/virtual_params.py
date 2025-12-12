from typing import List
from qcodes.instrument import Instrument
from qcodes.parameters import Parameter


class BaseVoltageSource(Instrument):
    """
    Abstract Instrument representing voltage source with some range
    """

    def __init__(self, name: str):
        super().__init__(name)

        self.voltage = self.add_parameter("voltage", abstract=True)
        self.phase = self.add_parameter("phase", abstract=True)


class DensityParameter:
    def __init__(
        self,
        displacement: Parameter,
        capacitances: List[float],
        voltages: List[BaseVoltageSource],
    ):
        self.D = displacement
        self.Caps = capacitances
        self.Vsrcs = voltages

    def get_dennsity(self) -> float:
        sum = 0
        for i in range(len(self.Caps)):
            sum += self.Caps[i] * self.Vsrcs[i].voltage()
        return sum

    def set_density(self, setpoint: float):
        raise NotImplementedError


def monkey_time():
    return 5


class Sum:
    def __init__(self, name, param1: Parameter, param2: Parameter):
        self.full_name = name
        self.p1 = param1
        self.p2 = param2
        self.summ = 0
        self.diff = 0

    def __call__(self, val=None):

        if val is None:
            return self.p1() + self.p2()

        else:
            self.summ = val
            self.diff = self.p1() - self.p2()
            p1val = (self.summ + self.diff) / 2
            p2val = (self.summ - self.diff) / 2
            self.p1(p1val)
            self.p2(p2val)


class Diff:
    def __init__(self, name, param1, param2):
        self.full_name = name
        self.p1 = param1
        self.p2 = param2
        self.summ = 0
        self.diff = 0

    def __call__(self, val=None):
        if val is None:
            return self.p1() - self.p2()
        else:
            self.diff = val
            sumval = self.p1() + self.p2()
            p1val = (sumval + self.diff) / 2
            p2val = (sumval - self.diff) / 2
            self.p1(p1val)
            self.p2(p2val)

from barreralabdrivers.utils.nanopositioner_mover import NanoPositioner
from barreralabdrivers.drivers.rotator import Rotator


nano = NanoPositioner(
    ip="192.168.1.1",
    n_axes=1,
)

rotator = Rotator(
    name="rotator",
    nanopositioner=nano,
    axis=0,
)
"""
QCoDeS driver for the Oxford Mercury iPS
written by Eames Donovan, Sam Paudel based on the drivers by eliasankerhold on https://github.com/eliasankerhold/BlueFTC
June 2026 revision 0.1: basic identification and read functionality
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
import sys
sys.path.append(
    r"C:\Users\barreralab\AppData\Roaming\Python\Python39\site-packages"
)
from blueftc.BlueforsController import BlueFTController

log = logging.getLogger(__name__)

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# define required configuration

class BlueforsTemperatureController(VisaInstrument):
    def __init__(
        self, name: str, address: str, terminator: str = "\n", **kwargs: Any
    ) -> None:
        controller = BlueFTController(ip=IP_ADDRESS, port=PORT_NUMBER, key=API_KEY, 
                              mixing_chamber_channel_id=MXC_ID, mixing_chamber_heater_id=HEATER_ID)
        
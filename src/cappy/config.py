"""
configuration file
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Data Paths
DATA_MAIN_PATH = ROOT / "Data"
DATA_PATH = DATA_MAIN_PATH / "data"
DATA2_PATH = DATA_MAIN_PATH / "data2"
BGBSO1_1 = DATA_MAIN_PATH / "BGBSO1_1"
BGBSO1_2 = DATA_MAIN_PATH / "BGBSO1_2"
BGBSO2_1_1 = DATA_MAIN_PATH / "BGBSO2_1_1"
BGBSO2_1_1_Onedrive = "C:/Users/barreralab/University of Toronto/Sergio de la Barrera - BarreraLab/Eames-Donovan/BG_BSO Batch 2 Measurements/BG_BS0_2_1_1/Data"
ANTOINE_Delta_F = "C:/Users/barreralab/University of Toronto/Sergio de la Barrera - BarreraLab/Eames-Donovan/Antoine batch Delta measurements/Delta F/Data"
ANTOINE_Delta_D = "C:/Users/barreralab/University of Toronto/Sergio de la Barrera - BarreraLab/Eames-Donovan/Antoine batch Delta measurements/Delta D/Data"
thermocoaxLeakage = DATA_MAIN_PATH / "thermocoaxLeakage"
deltaC = DATA_MAIN_PATH / "deltaC"
DATA_FOUR_TERM_PATH = DATA_MAIN_PATH / "data4term"

# YAML files for qcodes station configurations
TEST_STATION_CONFIG = ROOT / "src" / "cappy" / "station_configs" / "insts.yml"
COOL_STATION_CONFIG = ROOT / "src" / "cappy" / "station_configs" / "ppms_exps.yml"
DUAL_HEMT_STATION_CONFIG = ROOT / "src" / "cappy" / "station_configs" / "dual_hemt.yml"
FOURTERM_STATION_CONFIG = ROOT / "src" / "cappy" / "station_configs" / "4term.yml"
VTI_CONFIG = ROOT / "src" / "cappy" / "station_configs" / "oxfordVTI.yml"


# SCPI Address Generation for flexible instrument setups
# Note: this is not encapsulated in a library because addresses can be machine and system specific.
# This repo template assumes data collection is done on the same machine. Data analysis is agnostic.


def USB_ADDR(port_number: int):
    return f"ASRL{port_number}::INSTR"


def ETH_ADDR(ip_address: str):
    return f"TCPIP::{ip_address}::inst0::INSTR"


def GPIB_ADDR(gpib_address: int):
    return f"GPIB0::{gpib_address}::INSTR"


HELLO = "hiya can you see me"

"""Constants for the Indygo Pool integration."""

import json
from logging import Logger, getLogger
from pathlib import Path

LOGGER: Logger = getLogger(__package__)

DOMAIN = "indygo_pool"
NAME = "Indygo Pool"
VERSION: str = json.loads((Path(__file__).parent / "manifest.json").read_text())[
    "version"
]

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_POOL_ID = "pool_id"
CONF_SCAN_INTERVAL = "scan_interval"

# Default polling interval, in seconds (matches the previous hardcoded value).
DEFAULT_SCAN_INTERVAL = 300

PROGRAM_TYPE_FILTRATION = 4
# Spotlight / pool light program. Confirmed on LR-PC hardware: the vendor apps
# write programCharacteristics.mode on this program to switch the light on (1)
# and off (0). Such programs also carry metadata.spotlightType.
PROGRAM_TYPE_LIGHTING = 2

# programCharacteristics.mode values.
PROGRAM_MODE_OFF = 0
PROGRAM_MODE_ON = 1
PROGRAM_MODE_AUTO = 2

# Only variable-speed pump (LR-PC-VS*) filtration programs carry a speed.
# Confirmed on LR-PC-VS2 (#284): the vendor app writes defaultProgramSpeed and
# onSpeed together (1-3), and rule holds the management type.
VARIABLE_SPEED_FIELD = "defaultProgramSpeed"
ON_SPEED_FIELD = "onSpeed"
RULE_FIELD = "rule"

# programCharacteristics.rule values (management type).
PROGRAM_RULE_SCHEDULE = 0
PROGRAM_RULE_THERMO_ADAPTIVE = 1
PROGRAM_RULE_VARIABLE_SPEED = 2

# Live speed reported by variable-speed pumps in pool[0].value.
PUMP_SPEED_STATES = {0: "stopped", 1: "speed_1", 2: "speed_2", 3: "speed_3"}

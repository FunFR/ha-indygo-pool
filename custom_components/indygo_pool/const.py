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

PROGRAM_TYPE_FILTRATION = 4
# Spotlight / pool light program. Confirmed on LR-PC hardware: the vendor apps
# write programCharacteristics.mode on this program to switch the light on (1)
# and off (0). Such programs also carry metadata.spotlightType.
PROGRAM_TYPE_LIGHTING = 2

# programCharacteristics.mode values.
PROGRAM_MODE_OFF = 0
PROGRAM_MODE_ON = 1
PROGRAM_MODE_AUTO = 2

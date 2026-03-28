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

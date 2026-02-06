"""Constants for the Indygo Pool integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "indygo_pool"
NAME = "Indygo Pool"
VERSION = "1.3.0"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_POOL_ID = "pool_id"

PROGRAM_TYPE_FILTRATION = 4

ATTRIBUTION = "Data provided by MyIndygo"

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
-------------------------------------------------------------------
"""

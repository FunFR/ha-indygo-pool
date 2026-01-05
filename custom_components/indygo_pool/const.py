"""Constants for the Indygo Pool integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "indygo_pool"
NAME = "Indygo Pool"
VERSION = "1.0.8"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_POOL_ID = "pool_id"

ATTRIBUTION = "Data provided by MyIndygo"

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
-------------------------------------------------------------------
"""

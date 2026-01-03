"""Binary sensor platform for Indygo Pool."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .coordinator import IndygoPoolDataUpdateCoordinator
from .entity import IndygoPoolEntity

ENTITY_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="filtration",
        name="Filtration",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key="electrolyser",
        name="Electrolyser",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key="boost",
        name="Boost Mode",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary_sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        IndygoPoolBinarySensor(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class IndygoPoolBinarySensor(IndygoPoolEntity, BinarySensorEntity):
    """Indygo Pool binary_sensor class."""

    def __init__(
        self,
        coordinator: IndygoPoolDataUpdateCoordinator,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary_sensor is on."""
        # This will be mapped to the actual data structure once api.py is implemented
        return None

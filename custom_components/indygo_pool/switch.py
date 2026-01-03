"""Switch platform for Indygo Pool."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IndygoPoolDataUpdateCoordinator
from .entity import IndygoPoolEntity

ENTITY_DESCRIPTIONS = (
    SwitchEntityDescription(
        key="boost_toggle",
        name="Boost",
        icon="mdi:rocket",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        IndygoPoolSwitch(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class IndygoPoolSwitch(IndygoPoolEntity, SwitchEntity):
    """Indygo Pool switch class."""

    def __init__(
        self,
        coordinator: IndygoPoolDataUpdateCoordinator,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        return None

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        # await self.coordinator.client.async_set_boost(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        # await self.coordinator.client.async_set_boost(False)
        await self.coordinator.async_request_refresh()

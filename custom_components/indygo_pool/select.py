"""Select platform for Indygo Pool."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IndygoPoolDataUpdateCoordinator
from .entity import IndygoPoolEntity

ENTITY_DESCRIPTIONS = (
    SelectEntityDescription(
        key="filtration_mode",
        name="Filtration Mode",
        options=["Off", "Auto", "On", "Forced"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        IndygoPoolSelect(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class IndygoPoolSelect(IndygoPoolEntity, SelectEntity):
    """Indygo Pool select class."""

    def __init__(
        self,
        coordinator: IndygoPoolDataUpdateCoordinator,
        entity_description: SelectEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        # This will call the API once implemented
        # await self.coordinator.client.async_set_filtration_mode(option)
        await self.coordinator.async_request_refresh()

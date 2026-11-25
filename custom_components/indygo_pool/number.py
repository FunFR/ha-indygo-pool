"""Number platform for Indygo Pool."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ELECTROLYSER_MODE_PERCENTAGE
from .coordinator import IndygoPoolDataUpdateCoordinator
from .entity import IndygoPoolEntity, async_set_electrolyser
from .models import IndygoModuleData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""
    coordinator: IndygoPoolDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.data:
        return

    async_add_entities(
        IndygoPoolProductionSetpointNumber(coordinator, module_id)
        for module_id, module in coordinator.data.modules.items()
        if module.electrolyser_output
    )


class IndygoPoolProductionSetpointNumber(IndygoPoolEntity, NumberEntity):
    """Share of its maximum output the electrolyser produces.

    It only drives production in percentage mode, so it is unavailable in
    the other modes, as in the MyIndygo app.
    """

    _attr_translation_key = "production_setpoint"
    _attr_icon = "mdi:water-percent"
    # Observed: the cloud raises any lower value to 10.
    _attr_native_min_value = 10
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self, coordinator: IndygoPoolDataUpdateCoordinator, module_id: str
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, module_id)
        self._attr_unique_id = self._build_unique_id("production_setpoint_control")
        self.entity_id = f"number.{self.device_name_slug}_production_setpoint"

    def _module(self) -> IndygoModuleData | None:
        data = self.coordinator.data
        if not data or self._module_id is None:
            return None
        return data.modules.get(self._module_id)

    def _ipx_data(self) -> dict:
        module = self._module()
        return module.electrolyser_settings if module else {}

    @property
    def available(self) -> bool:
        """Return True only in percentage mode."""
        return (
            super().available
            and self._ipx_data().get("electrolyzerMode") == ELECTROLYSER_MODE_PERCENTAGE
        )

    @property
    def native_value(self) -> float | None:
        """Return the production setpoint."""
        value = self._ipx_data().get("percentageSetpoint")
        return value if isinstance(value, int | float) else None

    async def async_set_native_value(self, value: float) -> None:
        """Send the new production setpoint."""
        module = self._module()
        if module is None:
            return
        await async_set_electrolyser(
            self.coordinator, module, {"percentageSetpoint": int(value)}
        )
        await self.coordinator.async_request_refresh()

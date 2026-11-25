"""Tests for the IPX electrolyser controls (#344)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.indygo_pool.coordinator import IndygoPoolDataUpdateCoordinator
from custom_components.indygo_pool.entity import (
    async_set_electrolyser,
    filtration_is_stopped,
)
from custom_components.indygo_pool.models import (
    IndygoModuleData,
    IndygoPoolData,
    IndygoSensorData,
)
from custom_components.indygo_pool.number import IndygoPoolProductionSetpointNumber
from custom_components.indygo_pool.select import (
    IndygoPoolElectrolyserBoostSelect,
    IndygoPoolElectrolyserModeSelect,
)
from custom_components.indygo_pool.sensor import (
    SENSOR_TYPES,
    IndygoPoolSensor,
)

SETPOINT = 30
PH_INPUT = {"type": 6}
REDOX_INPUT = {"type": 7}


def _ipx_module(inputs: list[dict] | None = None, **ipx_data) -> IndygoModuleData:
    """IPX module shaped like the API: pH station first, electrolyser second."""
    settings = {
        "type": 4,
        "percentageSetpoint": SETPOINT,
        "electrolyzerMode": 1,
        "boostRemainingTime": 0,
        "boostEnabled": False,
    } | ipx_data
    return IndygoModuleData(
        id="ipx1",
        type="ipx",
        name="IPX",
        raw_data={
            "inputs": inputs if inputs is not None else [PH_INPUT],
            "outputs": [
                {"id": "out1", "ipxData": {"type": 1, "pHSetpoint": 7.4}},
                {"id": "out2", "ipxData": settings},
            ],
        },
    )


def _pump_module(running: bool) -> IndygoModuleData:
    module = IndygoModuleData(id="pc1", type="lr-pc", name="Pool Command")
    module.filtration_program = {"programCharacteristics": {"mode": 1}}
    module.pool_status["0"] = IndygoSensorData(
        key="filtration_status", value=1 if running else 0
    )
    return module


def _coordinator(*modules: IndygoModuleData) -> MagicMock:
    coordinator = MagicMock(spec=IndygoPoolDataUpdateCoordinator)
    coordinator.pool_device_id = None
    coordinator.data = IndygoPoolData(
        pool_id="pool1", modules={m.id: m for m in modules}
    )
    coordinator.client = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.config_entry = MagicMock(entry_id="entry1")
    coordinator.last_update_success = True
    return coordinator


# --- model ---------------------------------------------------------------


def test_electrolyser_output_is_found_by_its_settings():
    """The electrolyser is the output carrying an electrolyser mode."""
    assert _ipx_module().electrolyser_output["id"] == "out2"


def test_module_without_electrolyser():
    module = IndygoModuleData(id="m", type="ipx", name="IPX")
    assert module.electrolyser_output is None
    assert module.electrolyser_settings == {}


# --- production setpoint -------------------------------------------------


def test_setpoint_reads_the_electrolyser():
    entity = IndygoPoolProductionSetpointNumber(_coordinator(_ipx_module()), "ipx1")

    assert entity.native_value == SETPOINT
    assert entity.available


@pytest.mark.parametrize("mode", [0, 2])
def test_setpoint_unavailable_outside_percentage_mode(mode):
    """The setpoint only drives production in percentage mode."""
    coordinator = _coordinator(_ipx_module(electrolyzerMode=mode))
    entity = IndygoPoolProductionSetpointNumber(coordinator, "ipx1")

    assert not entity.available


@pytest.mark.asyncio
async def test_setpoint_write():
    coordinator = _coordinator(_ipx_module(), _pump_module(running=True))
    entity = IndygoPoolProductionSetpointNumber(coordinator, "ipx1")

    await entity.async_set_native_value(40.0)

    coordinator.client.async_set_ipx_data.assert_awaited_once_with(
        "out2", {"percentageSetpoint": 40}
    )
    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_write_refused_while_filtration_stopped():
    """Like the app, nothing is sent while the pump is stopped."""
    coordinator = _coordinator(_ipx_module(), _pump_module(running=False))
    entity = IndygoPoolProductionSetpointNumber(coordinator, "ipx1")

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_set_native_value(40.0)

    assert err.value.translation_key == "filtration_stopped"
    coordinator.client.async_set_ipx_data.assert_not_called()


# --- mode ----------------------------------------------------------------


def test_mode_offers_auto_only_with_a_redox_sensor():
    without = IndygoPoolElectrolyserModeSelect(
        _coordinator(_ipx_module()), "ipx1", "IPX"
    )
    with_redox = IndygoPoolElectrolyserModeSelect(
        _coordinator(_ipx_module(inputs=[REDOX_INPUT])), "ipx1", "IPX"
    )

    assert without.options == ["off", "percentage"]
    assert with_redox.options == ["off", "percentage", "auto"]
    assert without.current_option == "percentage"


def test_mode_keeps_auto_when_already_in_auto():
    """A module already in AUTO must be able to show it."""
    coordinator = _coordinator(_ipx_module(electrolyzerMode=2))
    entity = IndygoPoolElectrolyserModeSelect(coordinator, "ipx1", "IPX")

    assert "auto" in entity.options
    assert entity.current_option == "auto"


@pytest.mark.asyncio
async def test_mode_write():
    coordinator = _coordinator(_ipx_module(), _pump_module(running=True))
    entity = IndygoPoolElectrolyserModeSelect(coordinator, "ipx1", "IPX")

    with patch("custom_components.indygo_pool.select.async_call_later"):
        await entity.async_select_option("off")

    coordinator.client.async_set_ipx_data.assert_awaited_once_with(
        "out2", {"electrolyzerMode": 0}
    )


# --- boost ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("enabled", "minutes", "option", "remaining"),
    [
        (False, 0, "off", 0),
        (True, 0, "off", 0),
        (True, 600, "12h", 600),
        (True, 1000, "24h", 1000),
        # A cancelled boost keeps its last remaining time.
        (False, 720, "off", 0),
    ],
)
def test_boost_state(enabled, minutes, option, remaining):
    coordinator = _coordinator(
        _ipx_module(boostEnabled=enabled, boostRemainingTime=minutes)
    )
    entity = IndygoPoolElectrolyserBoostSelect(coordinator, "ipx1", "IPX")

    assert entity.current_option == option
    assert entity.extra_state_attributes == {"remaining_minutes": remaining}


@pytest.mark.asyncio
@pytest.mark.parametrize(("option", "command"), [("12h", 12), ("off", 0)])
async def test_boost_write(option, command):
    coordinator = _coordinator(_ipx_module(), _pump_module(running=True))
    entity = IndygoPoolElectrolyserBoostSelect(coordinator, "ipx1", "IPX")

    with patch("custom_components.indygo_pool.select.async_call_later"):
        await entity.async_select_option(option)

    coordinator.client.async_set_ipx_data.assert_awaited_once_with(
        "out2", {"boostCommand": command}
    )


# --- deprecated sensor ---------------------------------------------------


@pytest.mark.asyncio
async def test_production_setpoint_sensor_raises_a_repair_issue():
    """The read-only sensor is superseded by the number entity."""
    description = next(d for d in SENSOR_TYPES if d.key == "production_setpoint")
    entity = IndygoPoolSensor(_coordinator(_ipx_module()), description, "ipx1")
    entity.hass = MagicMock()

    with (
        patch("custom_components.indygo_pool.sensor.ir") as ir,
        patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity.async_added_to_hass",
            AsyncMock(),
        ),
    ):
        await entity.async_added_to_hass()

    issue = ir.async_create_issue.call_args
    assert issue.kwargs["translation_key"] == "deprecated_production_setpoint_sensor"


# --- edge cases ----------------------------------------------------------


def test_filtration_state_unknown_does_not_block():
    """Without data or a filtration module, writes are not refused."""
    assert not filtration_is_stopped(None)
    assert not filtration_is_stopped(IndygoPoolData(pool_id="p"))


@pytest.mark.asyncio
async def test_write_without_electrolyser_raises():
    module = IndygoModuleData(id="ipx1", type="ipx", name="IPX")

    with pytest.raises(HomeAssistantError) as err:
        await async_set_electrolyser(_coordinator(module), module, {})

    assert err.value.translation_key == "electrolyser_not_found"


@pytest.mark.asyncio
async def test_entities_without_settings():
    """A module that lost its electrolyser output reads nothing."""
    coordinator = _coordinator(_ipx_module(percentageSetpoint=None))
    number = IndygoPoolProductionSetpointNumber(coordinator, "ipx1")
    boost = IndygoPoolElectrolyserBoostSelect(coordinator, "ipx1", "IPX")
    coordinator.data.modules["ipx1"].raw_data["outputs"] = []

    assert number.native_value is None
    assert not boost.available
    assert boost.current_option is None

    coordinator.data.modules.clear()
    await number.async_set_native_value(40.0)
    coordinator.client.async_set_ipx_data.assert_not_called()


@pytest.mark.asyncio
async def test_deprecation_issue_dropped_on_removal():
    description = next(d for d in SENSOR_TYPES if d.key == "production_setpoint")
    entity = IndygoPoolSensor(_coordinator(_ipx_module()), description, "ipx1")
    entity.hass = MagicMock()

    with (
        patch("custom_components.indygo_pool.sensor.ir") as ir,
        patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity.async_will_remove_from_hass",
            AsyncMock(),
        ),
    ):
        await entity.async_will_remove_from_hass()

    ir.async_delete_issue.assert_called_once()


def test_setpoint_without_coordinator_data():
    coordinator = _coordinator(_ipx_module())
    entity = IndygoPoolProductionSetpointNumber(coordinator, "ipx1")
    coordinator.data = None

    assert entity.native_value is None

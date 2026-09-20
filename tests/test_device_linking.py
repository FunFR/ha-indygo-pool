"""Tests for how module devices link back to the parent pool device."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.indygo_pool.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_POOL_ID,
    DOMAIN,
)
from custom_components.indygo_pool.models import IndygoModuleData, IndygoPoolData


@pytest.mark.asyncio
async def test_module_device_links_to_pool_without_deprecation(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Module devices link to the pool by registry id, not by identifier tuple."""
    data = IndygoPoolData(pool_id="pool123", raw_data={})
    data.modules["ipx123"] = IndygoModuleData(
        id="ipx123",
        type="ipx",
        name="IPX Module",
        raw_data={"ipxData": {"deviceState": {"shutterEntry": True}}},
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "password",
            CONF_POOL_ID: "pool123",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.indygo_pool.IndygoPoolApiClient.async_get_data",
        new_callable=AsyncMock,
        return_value=data,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert "deprecated `via_device`" not in caplog.text, caplog.text

    device_reg = dr.async_get(hass)
    pool_device = device_reg.async_get_device_by_identifier(
        (DOMAIN, "pool123"), entry.entry_id
    )
    module_device = device_reg.async_get_device_by_identifier(
        (DOMAIN, "pool123_ipx123"), entry.entry_id
    )
    assert pool_device is not None
    assert module_device is not None
    assert module_device.via_device_id == pool_device.id

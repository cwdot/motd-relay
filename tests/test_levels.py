"""Per-level shortcut services stamp the right level."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from custom_components.motd_relay.const import DOMAIN

from .conftest import last_call


@pytest.mark.parametrize(
    "service_name,expected_level",
    [
        ("ok", "OK"),
        ("info", "Info"),
        ("warning", "Warning"),
        ("critical", "Critical"),
    ],
)
async def test_level_shortcut(
    hass: HomeAssistant, configured_entry, mock_publish, service_name, expected_level
) -> None:
    await hass.services.async_call(
        DOMAIN,
        service_name,
        {
            "service": "ha",
            "source": "x",
            "summary": "msg",
        },
        blocking=True,
    )
    _, payload, _ = last_call(mock_publish)
    assert payload["level"] == expected_level

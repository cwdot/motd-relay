"""Duration field produces an expires_at on the wire."""

from __future__ import annotations

import re
from datetime import datetime

from homeassistant.core import HomeAssistant

from custom_components.motd_relay.const import DOMAIN

from .conftest import last_call


async def test_duration_emits_expires_at(
    hass: HomeAssistant, configured_entry, mock_publish
) -> None:
    await hass.services.async_call(
        DOMAIN,
        "warning",
        {
            "source": "watcher",
            "summary": "Time-bound",
            "duration": "00:05:00",
        },
        blocking=True,
    )
    _, payload, _ = last_call(mock_publish)
    assert "expires_at" in payload

    # RFC3339 with offset, second precision.
    pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}([+-]\d{2}:\d{2}|Z)$"
    assert re.match(pattern, payload["expires_at"])

    # expires_at should be later than timestamp (sanity)
    ts = datetime.fromisoformat(payload["timestamp"])
    exp = datetime.fromisoformat(payload["expires_at"])
    assert (exp - ts).total_seconds() >= 5 * 60 - 1


async def test_no_duration_omits_expires_at(
    hass: HomeAssistant, configured_entry, mock_publish
) -> None:
    await hass.services.async_call(
        DOMAIN,
        "warning",
        {"source": "watcher", "summary": "indefinite"},
        blocking=True,
    )
    _, payload, _ = last_call(mock_publish)
    assert "expires_at" not in payload

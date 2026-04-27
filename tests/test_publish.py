"""Tests for motd_relay.publish service."""

from __future__ import annotations

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.motd_relay.const import DOMAIN

from .conftest import last_call


async def test_publish_builds_topic_and_payload(
    hass: HomeAssistant, configured_entry, mock_publish
) -> None:
    await hass.services.async_call(
        DOMAIN,
        "publish",
        {
            "service": "homeassistant",
            "source": "front_door",
            "level": "Warning",
            "summary": "Door unlocked",
            "details": ["battery=78%", "user=alice"],
            "alert_markdown": "**Front door** unlocked",
        },
        blocking=True,
    )

    topic, payload, kwargs = last_call(mock_publish)
    assert topic == "palantir/motd/input/homeassistant-front_door"
    assert kwargs == {"qos": 0, "retain": True}

    assert payload["service"] == "homeassistant"
    assert payload["source"] == "front_door"
    assert payload["level"] == "Warning"
    assert payload["summary"] == "Door unlocked"
    assert payload["details"] == "battery=78% | user=alice"
    assert payload["alert_markdown"] == "**Front door** unlocked"
    assert payload["version"].count("-") == 1
    assert "timestamp" in payload
    assert "expires_at" not in payload


async def test_publish_source_only_drops_service(
    hass: HomeAssistant, configured_entry, mock_publish
) -> None:
    await hass.services.async_call(
        DOMAIN,
        "publish",
        {
            "source": "front_door",
            "level": "OK",
            "summary": "All clear",
        },
        blocking=True,
    )

    topic, payload, _ = last_call(mock_publish)
    assert topic == "palantir/motd/input/front_door"
    assert "service" not in payload
    assert payload["source"] == "front_door"


async def test_publish_without_source_skips_suffix(
    hass: HomeAssistant, configured_entry, mock_publish
) -> None:
    await hass.services.async_call(
        DOMAIN,
        "publish",
        {
            "service": "homeassistant",
            "level": "Info",
            "summary": "service-only",
        },
        blocking=True,
    )
    topic, payload, _ = last_call(mock_publish)
    assert topic == "palantir/motd/input/homeassistant"
    assert payload["service"] == "homeassistant"
    assert "source" not in payload


async def test_publish_without_service_or_source_errors(
    hass: HomeAssistant, configured_entry, mock_publish
) -> None:
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "publish",
            {"level": "OK", "summary": "no key"},
            blocking=True,
        )
    assert mock_publish.await_count == 0


async def test_publish_string_details_passes_through(
    hass: HomeAssistant, configured_entry, mock_publish
) -> None:
    await hass.services.async_call(
        DOMAIN,
        "publish",
        {
            "service": "ha",
            "level": "OK",
            "summary": "ok",
            "details": "single line",
        },
        blocking=True,
    )
    _, payload, _ = last_call(mock_publish)
    assert payload["details"] == "single line"


async def test_publish_empty_details_when_omitted(
    hass: HomeAssistant, configured_entry, mock_publish
) -> None:
    await hass.services.async_call(
        DOMAIN,
        "publish",
        {"service": "ha", "level": "OK", "summary": "ok"},
        blocking=True,
    )
    _, payload, _ = last_call(mock_publish)
    assert payload["details"] == ""


async def test_publish_uses_custom_topic_prefix(
    hass: HomeAssistant, configured_with, mock_publish
) -> None:
    await configured_with(topic_prefix="custom/motd")

    await hass.services.async_call(
        DOMAIN,
        "publish",
        {
            "service": "ha",
            "source": "sensor",
            "level": "OK",
            "summary": "ok",
        },
        blocking=True,
    )
    topic, _, _ = last_call(mock_publish)
    assert topic == "custom/motd/ha-sensor"


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("service", "has space"),
        ("service", "has/slash"),
        ("source", "wild+card"),
        ("source", "wild#card"),
    ],
)
async def test_publish_rejects_unsafe_names(
    hass: HomeAssistant, configured_entry, mock_publish, field, bad_value
) -> None:
    payload = {
        "level": "OK",
        "summary": "ok",
        # Ensure the *other* key is present so we exercise the name
        # validator, not the "at least one is required" guard.
        ("service" if field == "source" else "source"): "ok_name",
        field: bad_value,
    }
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "publish", payload, blocking=True)
    assert mock_publish.await_count == 0

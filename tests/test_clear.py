"""motd_relay.clear publishes empty retained payload."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.motd_relay.const import DOMAIN


async def test_clear_publishes_empty_retained(
    hass: HomeAssistant, configured_entry, mock_publish
) -> None:
    await hass.services.async_call(
        DOMAIN,
        "clear",
        {"service": "ha", "source": "front_door"},
        blocking=True,
    )

    args, kwargs = mock_publish.await_args
    _hass, topic, payload = args[0], args[1], args[2]
    assert topic == "palantir/motd/input/ha-front_door"
    assert payload == ""
    assert kwargs == {"qos": 0, "retain": True}


async def test_clear_source_only(hass: HomeAssistant, configured_entry, mock_publish) -> None:
    await hass.services.async_call(
        DOMAIN,
        "clear",
        {"source": "thing"},
        blocking=True,
    )
    args, _ = mock_publish.await_args
    assert args[1] == "palantir/motd/input/thing"

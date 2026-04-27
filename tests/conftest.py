"""Test fixtures for motd_relay."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.motd_relay.const import (
    CONF_TOPIC_PREFIX,
    DEFAULT_TOPIC_PREFIX,
    DOMAIN,
)

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make HA load custom_components/motd_relay during tests."""
    yield


@pytest.fixture
def mock_publish():
    """Patch mqtt.async_publish + mark MQTT as loaded.

    The integration's runtime publish path goes through
    `homeassistant.components.mqtt.async_publish`. We patch it where it's
    looked up (inside our integration module) and pretend the MQTT
    component is loaded so the load-guard passes.
    """
    publish_mock = AsyncMock()
    with (
        patch("custom_components.motd_relay.mqtt.async_publish", publish_mock),
        patch("custom_components.motd_relay.mqtt.DOMAIN", "mqtt"),
    ):
        yield publish_mock


async def _add_entry(
    hass: HomeAssistant,
    *,
    topic_prefix: str = DEFAULT_TOPIC_PREFIX,
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={},
        options={CONF_TOPIC_PREFIX: topic_prefix},
    )
    entry.add_to_hass(hass)
    # Mark MQTT as a loaded component so the runtime guard passes.
    hass.config.components.add("mqtt")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
async def configured_entry(hass: HomeAssistant, mock_publish) -> MockConfigEntry:
    return await _add_entry(hass)


@pytest.fixture
async def configured_with(hass: HomeAssistant, mock_publish):
    """Factory that lets a test customize topic_prefix."""

    async def _make(*, topic_prefix: str = DEFAULT_TOPIC_PREFIX) -> MockConfigEntry:
        return await _add_entry(hass, topic_prefix=topic_prefix)

    return _make


def last_call(publish_mock: AsyncMock) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Return (topic, decoded JSON payload, kwargs) from the most recent publish."""
    assert publish_mock.await_count > 0
    args, kwargs = publish_mock.await_args
    # Signature: async_publish(hass, topic, payload, qos=..., retain=...)
    _hass, topic, payload = args[0], args[1], args[2]
    decoded = json.loads(payload) if payload else {}
    return topic, decoded, kwargs

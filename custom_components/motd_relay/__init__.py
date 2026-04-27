"""MOTD Relay integration.

Bridges Home Assistant service calls to palantir's retained-MQTT MOTD bus.
The wire format mirrors palantir/internal/statuspublisher exactly:
topic `<prefix>/<service>` (or `<prefix>/<service>-<source>` when a source
is given), retained JSON payload with a per-publisher `<unix>-<counter>`
version that the consumer uses to dedup and supersede.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_ALERT_MARKDOWN,
    ATTR_DETAILS,
    ATTR_DURATION,
    ATTR_LEVEL,
    ATTR_SERVICE,
    ATTR_SOURCE,
    ATTR_SUMMARY,
    CONF_TOPIC_PREFIX,
    DEFAULT_TOPIC_PREFIX,
    DOMAIN,
    LEVEL_CRITICAL,
    LEVEL_INFO,
    LEVEL_OK,
    LEVEL_WARNING,
    LEVELS,
    SERVICE_CLEAR,
    SERVICE_CRITICAL,
    SERVICE_INFO,
    SERVICE_OK,
    SERVICE_PUBLISH,
    SERVICE_WARNING,
)

_LOGGER = logging.getLogger(__name__)

# service / source must be safe to embed in an MQTT topic. The motd consumer
# stores entries keyed by `<service>-<source>`, so we restrict to the same
# character set that internal palantir publishers use (no `/`, no wildcards).
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _validate_name(value: Any, field: str) -> str:
    if value is None or value == "":
        return ""
    if not isinstance(value, str) or not _NAME_RE.match(value):
        raise vol.Invalid(f"{field} must match {_NAME_RE.pattern}")
    return value


def _normalize_details(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list | tuple):
        return " | ".join(str(item) for item in value)
    return str(value)


_PUBLISH_FIELDS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_SERVICE): vol.All(cv.string, lambda v: _validate_name(v, ATTR_SERVICE)),
        vol.Optional(ATTR_SOURCE): vol.All(cv.string, lambda v: _validate_name(v, ATTR_SOURCE)),
        vol.Required(ATTR_SUMMARY): cv.string,
        vol.Optional(ATTR_DETAILS): vol.Any(cv.string, [cv.string]),
        vol.Optional(ATTR_ALERT_MARKDOWN): cv.string,
        vol.Optional(ATTR_DURATION): cv.time_period,
    }
)

_PUBLISH_SCHEMA = _PUBLISH_FIELDS_SCHEMA.extend(
    {
        vol.Required(ATTR_LEVEL): vol.In(LEVELS),
    }
)

_CLEAR_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_SERVICE): vol.All(cv.string, lambda v: _validate_name(v, ATTR_SERVICE)),
        vol.Optional(ATTR_SOURCE): vol.All(cv.string, lambda v: _validate_name(v, ATTR_SOURCE)),
    }
)

_FIXED_LEVEL_SERVICES: tuple[tuple[str, str], ...] = (
    (SERVICE_OK, LEVEL_OK),
    (SERVICE_INFO, LEVEL_INFO),
    (SERVICE_WARNING, LEVEL_WARNING),
    (SERVICE_CRITICAL, LEVEL_CRITICAL),
)


class _VersionGenerator:
    """Mirrors statuspublisher.nextVersion: <unix>-<counter> per publisher."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._last_unix: int = 0
        self._counter: int = 0

    async def next(self) -> str:
        async with self._lock:
            now = int(datetime.now(UTC).timestamp())
            if now > self._last_unix:
                self._last_unix = now
                self._counter = 1
            else:
                self._counter += 1
            return f"{self._last_unix}-{self._counter}"


class _Relay:
    """Per-config-entry state: settings + version generator."""

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry
        self.versioner = _VersionGenerator()

    @property
    def topic_prefix(self) -> str:
        return self.entry.options.get(
            CONF_TOPIC_PREFIX, self.entry.data.get(CONF_TOPIC_PREFIX, DEFAULT_TOPIC_PREFIX)
        )


def _build_topic(prefix: str, service: str, source: str) -> str:
    # Topic suffix mirrors the dedup key the motd consumer uses:
    # service+source → "service-source", otherwise whichever one is set.
    if service and source:
        return f"{prefix}/{service}-{source}"
    return f"{prefix}/{service or source}"


def _now_iso() -> str:
    # RFC3339 with offset, second precision — matches palantir's
    # time.Format(time.RFC3339).
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")


def _expiry_iso(duration: timedelta) -> str:
    return (datetime.now(UTC).astimezone() + duration).isoformat(timespec="seconds")


def _pick_relay(hass: HomeAssistant) -> _Relay:
    relays: dict[str, _Relay] = hass.data.get(DOMAIN, {})
    if not relays:
        raise HomeAssistantError("MOTD Relay is not configured")
    if len(relays) > 1:
        raise HomeAssistantError("Multiple MOTD Relay entries are not supported")
    return next(iter(relays.values()))


async def _async_publish(hass: HomeAssistant, level: str, call: ServiceCall) -> None:
    if mqtt.DOMAIN not in hass.config.components:
        raise HomeAssistantError("MQTT integration is not loaded")

    relay = _pick_relay(hass)
    data = call.data

    service_name = data.get(ATTR_SERVICE, "") or ""
    source = data.get(ATTR_SOURCE, "") or ""
    if not service_name and not source:
        raise HomeAssistantError("at least one of `service` or `source` must be set")
    summary = data[ATTR_SUMMARY]
    details = _normalize_details(data.get(ATTR_DETAILS))
    alert_markdown = data.get(ATTR_ALERT_MARKDOWN, "") or ""
    duration: timedelta | None = data.get(ATTR_DURATION)

    version = await relay.versioner.next()

    payload: dict[str, Any] = {
        "level": level,
        "summary": summary,
        "details": details,
        "version": version,
        "timestamp": _now_iso(),
    }
    if service_name:
        payload["service"] = service_name
    if source:
        payload["source"] = source
    if alert_markdown:
        payload["alert_markdown"] = alert_markdown
    if duration is not None:
        payload["expires_at"] = _expiry_iso(duration)

    topic = _build_topic(relay.topic_prefix, service_name, source)
    await mqtt.async_publish(
        hass, topic, json.dumps(payload, separators=(",", ":")), qos=0, retain=True
    )
    _LOGGER.info("Published MOTD %s to %s (version=%s)", level, topic, version)


async def _async_clear(hass: HomeAssistant, call: ServiceCall) -> None:
    if mqtt.DOMAIN not in hass.config.components:
        raise HomeAssistantError("MQTT integration is not loaded")

    relay = _pick_relay(hass)
    data = call.data

    service_name = data.get(ATTR_SERVICE, "") or ""
    source = data.get(ATTR_SOURCE, "") or ""
    if not service_name and not source:
        raise HomeAssistantError("at least one of `service` or `source` must be set")
    topic = _build_topic(relay.topic_prefix, service_name, source)
    # Empty retained payload tells the broker to drop the retained value.
    await mqtt.async_publish(hass, topic, "", qos=0, retain=True)
    _LOGGER.info("Cleared retained MOTD on %s", topic)


def _make_handler(
    hass: HomeAssistant, level: str | None
) -> Callable[[ServiceCall], Coroutine[Any, Any, None]]:
    async def _handle(call: ServiceCall) -> None:
        # When level is None we're handling the explicit "publish" service
        # which carries the level in call.data; otherwise it's one of the
        # fixed-level shortcuts.
        chosen_level = level if level is not None else call.data[ATTR_LEVEL]
        await _async_publish(hass, chosen_level, call)

    return _handle


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_PUBLISH):
        return

    hass.services.async_register(
        DOMAIN, SERVICE_PUBLISH, _make_handler(hass, None), schema=_PUBLISH_SCHEMA
    )

    for service_name, level in _FIXED_LEVEL_SERVICES:
        hass.services.async_register(
            DOMAIN, service_name, _make_handler(hass, level), schema=_PUBLISH_FIELDS_SCHEMA
        )

    async def _clear_call(call: ServiceCall) -> None:
        await _async_clear(hass, call)

    hass.services.async_register(DOMAIN, SERVICE_CLEAR, _clear_call, schema=_CLEAR_SCHEMA)


def _async_unregister_services(hass: HomeAssistant) -> None:
    for service_name in (
        SERVICE_PUBLISH,
        SERVICE_OK,
        SERVICE_INFO,
        SERVICE_WARNING,
        SERVICE_CRITICAL,
        SERVICE_CLEAR,
    ):
        if hass.services.has_service(DOMAIN, service_name):
            hass.services.async_remove(DOMAIN, service_name)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    relay = _Relay(entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = relay
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    relays: dict[str, _Relay] = hass.data.get(DOMAIN, {})
    relays.pop(entry.entry_id, None)
    if not relays:
        _async_unregister_services(hass)
        hass.data.pop(DOMAIN, None)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

"""Version generator: <unix>-<counter>, mirroring statuspublisher."""

from __future__ import annotations

import json
from datetime import UTC
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.motd_relay.const import DOMAIN


async def _publish_n(hass: HomeAssistant, n: int) -> None:
    for i in range(n):
        await hass.services.async_call(
            DOMAIN,
            "ok",
            {"service": "ha", "summary": f"msg {i}"},
            blocking=True,
        )


def _versions(mock_publish) -> list[str]:
    versions: list[str] = []
    for call in mock_publish.await_args_list:
        payload = call.args[2]
        versions.append(json.loads(payload)["version"])
    return versions


async def test_counter_increments_within_same_second(
    hass: HomeAssistant, configured_entry, mock_publish
) -> None:
    fixed_now = 1745764421.5

    class _DT:
        @staticmethod
        def now(tz=None):
            from datetime import datetime

            return datetime.fromtimestamp(fixed_now, tz=tz or UTC)

    with patch("custom_components.motd_relay.datetime", _DT):
        await _publish_n(hass, 3)

    v1, v2, v3 = _versions(mock_publish)
    assert v1 == "1745764421-1"
    assert v2 == "1745764421-2"
    assert v3 == "1745764421-3"


async def test_counter_resets_when_clock_advances(
    hass: HomeAssistant, configured_entry, mock_publish
) -> None:
    """Two publishes one second apart should produce -1 and -1."""
    timeline = [
        # Each publish calls datetime.now() in: version (1x) + timestamp (1x).
        # Provide 4 entries — 2 per publish, both rounding to the same second
        # within a single publish, advancing between publishes.
        1745764421.0,  # publish 1: version
        1745764421.1,  # publish 1: timestamp
        1745764422.0,  # publish 2: version
        1745764422.1,  # publish 2: timestamp
    ]
    it = iter(timeline)

    class _DT:
        @staticmethod
        def now(tz=None):
            from datetime import datetime

            return datetime.fromtimestamp(next(it), tz=tz or UTC)

    with patch("custom_components.motd_relay.datetime", _DT):
        await _publish_n(hass, 2)

    v1, v2 = _versions(mock_publish)
    assert v1 == "1745764421-1"
    assert v2 == "1745764422-1"

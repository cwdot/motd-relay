# MOTD Relay

Home Assistant custom integration that exposes services for publishing
status updates onto [palantir](https://github.com/cwdot/palantir)'s MOTD
MQTT bus.

## What it does

Each service call becomes a single retained MQTT publish in the format
palantir's `motd` plugin already understands:

- **Topic:** `<topic_prefix>/<service>-<source>` when both are given,
  otherwise `<topic_prefix>/<service>` or `<topic_prefix>/<source>`.
  At least one of `service` / `source` must be set.
- **Payload:** JSON `{service?, source?, level, summary, details, version, timestamp, alert_markdown?, expires_at?}`
- **Retain:** true, **QoS:** 0

The integration tracks `version` itself (`<unix>-<counter>`, mirroring
palantir's `statuspublisher.nextVersion`) so messages always supersede
correctly.

## Install via HACS

1. HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/cwdot/motd-relay` as type **Integration**
3. Install **MOTD Relay**, restart Home Assistant
4. Settings → Devices & Services → Add Integration → **MOTD Relay**
5. Set the **Topic prefix** (default `palantir/motd/input`).

MQTT must be configured separately — this integration depends on it.

## Services

All publish-family services accept the same fields except for level:

| Service | Level |
|---|---|
| `motd_relay.publish` | required (`OK` / `Info` / `Warning` / `Critical`) |
| `motd_relay.ok` | `OK` |
| `motd_relay.info` | `Info` |
| `motd_relay.warning` | `Warning` |
| `motd_relay.critical` | `Critical` |
| `motd_relay.clear` | (drops the retained value for the given service+source) |

### Fields

| Field | Required | Notes |
|---|---|---|
| `service` | one of `service`/`source` is required | Service identifier. Must match `[A-Za-z0-9_-]+`. |
| `source` | one of `service`/`source` is required | Sub-source identifier; reuse it to supersede a previous status. Must match `[A-Za-z0-9_-]+`. |
| `summary` | yes | One-line summary. |
| `details` | no | List of strings, or a single string (wrapped into a one-element list). |
| `alert_markdown` | no | Markdown rendered into palantir's MOTD alert sensor. |
| `duration` | no | Time period (e.g. `"00:05:00"`, `30s`). Adds an `expires_at` to the payload; palantir drops the entry once the deadline passes. |
| `url` | no | URL the rendered MOTD title links to. When the message also carries `actions`, this is the URL a push notification opens on tap. Emitted on the wire as `link`. |
| `actions` | no | List of actionable-notification buttons. Presence of `actions` makes palantir fire a push notification (to its configured notify targets). See below. |

### Actions

Each action mirrors a Home Assistant companion [actionable
notification](https://companion.home-assistant.io/docs/notifications/actionable-notifications)
button — the contract is identical on iOS and Android:

| Key | Required | Notes |
|---|---|---|
| `action` | yes | Action identifier received in the `mobile_app_notification_action` event. Use `URI` to open `uri` directly. |
| `title` | yes | User-visible button label. |
| `uri` | no | Opened when `action` is `URI` (a URL or a Lovelace path like `/lovelace/cameras`). Also renders as a bullet link in the MOTD details sensor. |
| `icon` | no | Android button icon, e.g. `mdi:cctv`. |
| `destructive` | no | iOS: render the button in red. |

Actions ride through palantir unchanged: on receipt, palantir forwards `url`
and `actions` as a push notification to every notify target its `notifier`
plugin is configured with. The push fires only when the message's content
changes (not on routine republishes).

### Example

```yaml
- service: motd_relay.warning
  data:
    source: front_door
    summary: Front door unlocked for 10 min
    details:
      - battery=78%
      - last_user=alice
    duration: "00:05:00"
```

Produces this retained publish on `palantir/motd/input/front_door`:

```json
{
  "source": "front_door",
  "level": "Warning",
  "summary": "Front door unlocked for 10 min",
  "details": ["battery=78%", "last_user=alice"],
  "version": "1745764421-1",
  "timestamp": "2026-04-27T08:53:41-04:00",
  "expires_at": "2026-04-27T08:58:41-04:00"
}
```

### Example with URL + actions

```yaml
- service: motd_relay.critical
  data:
    source: front_door
    summary: Front door forced open
    url: https://home.example.com/lovelace/security
    actions:
      - action: URI
        title: Open camera
        uri: https://home.example.com/lovelace/cameras
        icon: mdi:cctv
      - action: DISMISS_ALERT
        title: Dismiss
        destructive: true
```

Adds `link` and `actions` to the payload; palantir renders the entry and
forwards a push notification carrying the URL and buttons:

```json
{
  "source": "front_door",
  "level": "Critical",
  "summary": "Front door forced open",
  "details": [],
  "version": "1745764421-2",
  "timestamp": "2026-04-27T08:53:41-04:00",
  "link": "https://home.example.com/lovelace/security",
  "actions": [
    {"action": "URI", "title": "Open camera", "uri": "https://home.example.com/lovelace/cameras", "icon": "mdi:cctv"},
    {"action": "DISMISS_ALERT", "title": "Dismiss", "destructive": true}
  ]
}
```

## Development

```bash
make install   # create venv, install pytest + pytest-homeassistant-custom-component
make test      # run the test suite
make lint      # ruff check + format check
make run       # launch a dev HA with this integration symlinked
```

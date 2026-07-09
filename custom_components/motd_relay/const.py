DOMAIN = "motd_relay"

CONF_TOPIC_PREFIX = "topic_prefix"

DEFAULT_TOPIC_PREFIX = "palantir/motd/input"

LEVEL_OK = "OK"
LEVEL_INFO = "Info"
LEVEL_WARNING = "Warning"
LEVEL_CRITICAL = "Critical"
LEVELS = (LEVEL_OK, LEVEL_INFO, LEVEL_WARNING, LEVEL_CRITICAL)

SERVICE_PUBLISH = "publish"
SERVICE_OK = "ok"
SERVICE_INFO = "info"
SERVICE_WARNING = "warning"
SERVICE_CRITICAL = "critical"
SERVICE_CLEAR = "clear"

ATTR_SERVICE = "service"
ATTR_SOURCE = "source"
ATTR_LEVEL = "level"
ATTR_SUMMARY = "summary"
ATTR_DETAILS = "details"
ATTR_ALERT_MARKDOWN = "alert_markdown"
ATTR_DURATION = "duration"
ATTR_URL = "url"
ATTR_ACTIONS = "actions"

# Keys of a single action button on the wire. Mirrors palantir's
# notifications.NotificationActionButton JSON (uniform across iOS/Android):
# https://companion.home-assistant.io/docs/notifications/actionable-notifications
ACTION_ACTION = "action"
ACTION_TITLE = "title"
ACTION_URI = "uri"
ACTION_ICON = "icon"
ACTION_DESTRUCTIVE = "destructive"

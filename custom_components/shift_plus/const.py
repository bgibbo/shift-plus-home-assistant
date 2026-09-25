DOMAIN = "shift_plus"
NAME = "Shift +"
VERSION = "5.1.0"
STORAGE_VERSION = 1
STORAGE_KEY = "shift_plus.storage"
LEGACY_PUBLIC_STORAGE_KEY = "shift_plus"
PROTOCOL_VERSION = 1
PLATFORMS = ["sensor", "binary_sensor", "calendar", "button", "image"]

CONF_ROSTER_ID = "roster_id"
CONF_UNIT_ID = "unit_id"
CONF_INCLUDE_BRIEFING = "include_tour_briefing"
CONF_BOOK_ON_OFFSET = "book_on_offset_minutes"
CONF_BOOK_OFF_OFFSET = "book_off_offset_minutes"
ENTITLEMENT_PUBLIC_KEY = "s3tuQBypQYaaTeWUl24mz6DVQeGeQOgFKYlp3kBU7R4"
PAIRING_QR_LIFETIME_SECONDS = 300

EVENT_DATA_CHANGED = "shift_plus_data_changed"
SERVICE_ADD_OVERTIME = "add_overtime"
SERVICE_UPDATE_OVERTIME = "update_overtime"
SERVICE_DELETE_OVERTIME = "delete_overtime"
SERVICE_ADD_LEAVE = "add_annual_leave"
SERVICE_UPDATE_LEAVE = "update_annual_leave"
SERVICE_DELETE_LEAVE = "delete_annual_leave"
SERVICE_SET_ACTIVE_SCHEDULE = "set_active_schedule"
SERVICE_SYNC_NOW = "sync_now"
SERVICE_RESOLVE_CONFLICT = "resolve_conflict"

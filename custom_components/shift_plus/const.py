"""Constants for the Shift Plus integration."""

DOMAIN = "shift_plus"
NAME = "Shift Plus"
VERSION = "0.1.0"

CONF_ENTITLEMENT_PUBLIC_KEY = "entitlement_public_key"
CONF_NAME = "name"

ENTITLEMENT_ISSUER = "https://entitlements.shiftplus.ie"
ENTITLEMENT_AUDIENCE = "shift-plus-home-assistant"
ENTITLEMENT_PACKAGE = "ie.shiftplus.app"
ENTITLEMENT_PRODUCT = "shift_plus_premium"
ENTITLEMENT_TYPE = "premium"

PAIRING_TTL_SECONDS = 300
ENTITLEMENT_MAX_SECONDS = 8 * 24 * 60 * 60
NONCE_TTL_SECONDS = 10 * 60
MAX_OPERATIONS = 250
STORE_VERSION = 1
STORE_KEY_PREFIX = "shift_plus"

PLATFORMS = ["sensor"]

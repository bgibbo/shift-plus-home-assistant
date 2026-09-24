"""Constants for the Shift Plus integration."""

DOMAIN = "shift_plus"
NAME = "Shift +"
VERSION = "5.0.1"

CONF_ENTITLEMENT_PUBLIC_KEY = "entitlement_public_key"
CONF_NAME = "name"

# Public verification material only. The corresponding Ed25519 private key is
# held by Google Secret Manager and is never distributed with this integration.
PRODUCTION_ENTITLEMENT_PUBLIC_KEY = "s3tuQBypQYaaTeWUl24mz6DVQeGeQOgFKYlp3kBU7R4"

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

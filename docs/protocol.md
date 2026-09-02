# Shift Plus synchronization protocol v1

All JSON is UTF-8. Binary values use unpadded URL-safe base64.

## Pairing

The authenticated pairing page generates a five-minute QR payload containing:

- `protocol`, currently `1`
- Home Assistant config-entry ID and base URL
- single-use session ID and one-time secret
- Home Assistant X25519 public key
- UTC expiry

The app generates an X25519 key pair and device UUID. Both peers derive a
32-byte credential with HKDF-SHA256:

- input key material: X25519 shared secret
- salt: SHA-256 of the UTF-8 one-time secret
- info: `shift-plus-sync:<entry_id>:<device_id>`

The app submits its public key and a pairing-bound Premium entitlement to
`POST /api/shift_plus/<entry_id>/pairing/complete`.

## Authentication

Authenticated requests send a UUID nonce and an unpadded base64url
HMAC-SHA256 signature in `X-Shift-Plus-Nonce` and
`X-Shift-Plus-Signature`. The signed bytes are:

`UTF8(nonce) || LF || exact HTTP request body`

Sync also supplies `X-Shift-Plus-Device`. Nonces are accepted only once within
the replay window.

## Entitlements

The integration currently specifies a compact token as
`base64url(JSON claims).base64url(Ed25519 signature)`, where the signature covers
the ASCII payload segment. Claims bind the token to `ha_instance_id`,
`pairing_session_id`, `device_id`, `app_public_key`, and numeric UTC `exp`.

This encoding must be reconciled with the production entitlement issuer before
release. The Flutter project currently treats the token as opaque and does not
contain the issuer contract or verification key.

## Synchronization

`POST /api/shift_plus/<entry_id>/sync` exchanges operation records and a server
cursor. Records contain a type, ID, nullable payload, version vector, origin,
tombstone marker and idempotency operation ID. Dominating vectors replace older
records. Concurrent records use the same deterministic origin counter/replica
tie-break used by the app.

The current app repository emits `overtime` and `annual_leave` records. The
wire storage intentionally remains generic for compatible future record types.

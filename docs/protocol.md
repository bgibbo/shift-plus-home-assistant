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

The issuer returns compact JWS using Ed25519 (`alg=EdDSA`, `typ=JWT`):
`base64url(header).base64url(claims).base64url(signature)`. The signature covers
the two encoded segments and separator. The app treats this value as opaque.

The verifier requires the fixed Shift Plus issuer, Home Assistant audience,
Android package and Premium product IDs; `entitlement=premium`, `status=active`,
and `token_use=ha_pairing`; numeric `iat`, `nbf`, and `exp`; stable
`entitlement_id`, hashed purchase identity, installation ID and unique `jti`;
and exact HA entry, pairing session, device, and app X25519 public-key bindings.
Tokens live for 24 hours. A cancellation, refund, or revocation prevents the
backend issuing the next token, so synchronization stops no later than expiry.

Renewal uses `pairing_session_id=renew:<device_id>` and the established HMAC
credential. Home Assistant accepts only the same entitlement identity with a
strictly newer issue time, preventing identity swaps and token replay. The
Ed25519 private key exists only in the entitlement backend; the integration is
configured with the public verification key and fails closed without it.

## Synchronization

`POST /api/shift_plus/<entry_id>/sync` exchanges operation records and a server
cursor. Records contain a type, ID, nullable payload, version vector, origin,
tombstone marker and idempotency operation ID. Dominating vectors replace older
records. Concurrent records use the same deterministic origin counter/replica
tie-break used by the app.

The current app repository emits `overtime` and `annual_leave` records. The
wire storage intentionally remains generic for compatible future record types.

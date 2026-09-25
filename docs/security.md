# Security model

Shift + 5.1.0 retains the production 5.0.1 security architecture.

- Three-part JWT/JWS with EdDSA and Ed25519 verification
- Issuer, audience, Android package, Premium product, active status and token-use validation
- Issued-at, not-before and expiry validation
- HA entry, pairing session, installation, device and app-public-key binding
- Entitlement identity and token freshness checks during renewal
- Short-lived, single-use QR pairing
- X25519 key agreement and HKDF-SHA256 credential derivation
- HMAC-SHA256 authenticated requests
- Nonce replay protection
- Durable HA credential storage

The legacy Build 68 two-part `payload.signature` grant is rejected. The entitlement signing private key, Google Play credentials and purchase tokens are never stored in this repository.

The 5.1.0 storage migration copies an already-derived pairing credential without exposing or regenerating it. Public 5.0.1 did not retain installation ID; the first valid, fully bound production renewal establishes that additive field, after which installation changes are rejected.

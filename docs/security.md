# Security model and release checklist

## Stored data

Home Assistant stores its X25519 private key, derived device credentials,
entitlement expiries and synchronized records in its normal `.storage` area.
That directory must be protected as part of the Home Assistant installation.

The repository must never contain mobile signing keys, `key.properties`, Google
Play credentials, entitlement signing keys, Home Assistant tokens, `.storage`
data or configuration secrets.

## Before public release

- Deploy the private entitlement backend and map its production HTTPS hostname.
- Confirm the bundled production Ed25519 **public** key matches the entitlement
  service key endpoint.
- Verify entitlement issuance, pairing, renewal and expiry against the real app.
- Exercise pairing and sync against supported Home Assistant versions.
- Complete an independent protocol/security review.
- Pass unit tests, Ruff, HACS validation and Hassfest.
- Keep the bundled integration brand assets current.
- Create a signed/tagged GitHub release only after approval.

The Ed25519 private signing key belongs only in the entitlement service and must
never be copied into Home Assistant, the app, or this repository.

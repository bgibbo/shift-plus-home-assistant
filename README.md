# Shift Plus for Home Assistant

Private pre-release development repository for the official Home Assistant
counterpart to the Shift Plus Android app.

The integration provides local, bidirectional synchronization of supported
Shift Plus records. Pairing uses a short-lived QR code, X25519 key agreement,
HKDF-SHA256 credential derivation and HMAC-SHA256 authenticated requests.

> [!WARNING]
> This repository is not ready for public installation. The production Premium
> entitlement backend and Ed25519 public verification key must be deployed and
> tested end to end before release.

## Current capabilities

- Home Assistant UI configuration flow.
- Authenticated, five-minute QR pairing page.
- X25519/HKDF device credential establishment.
- Replay-resistant HMAC authentication.
- Persistent device and operation-log storage.
- Vector-clock merge of annual-leave and overtime records.
- Incremental synchronization cursors and idempotent operation acknowledgements.
- Premium entitlement refresh and self-revocation endpoints.
- Proof-of-identity endpoint for alternative Home Assistant URLs.
- Status sensor and `shift_plus.create_pairing` action.

## Development installation

Do not install this pre-release on a production Home Assistant system.

1. Copy `custom_components/shift_plus` into the Home Assistant `custom_components`
   directory.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration**, then select
   **Shift Plus**.
4. Configure the entitlement verification public key.
5. Run the `shift_plus.create_pairing` action and open the link in the resulting
   notification while signed in to Home Assistant.
6. Scan the displayed QR from the Home Assistant screen in Shift Plus.

## Security

- Pairing secrets live for five minutes and are single use.
- Per-device credentials are derived locally and never appear in the QR.
- Sync, renewal and revocation requests are signed over the exact request body.
- Replayed nonces are rejected.
- Alternative endpoints must prove possession of the paired credential.
- Pairing fails closed when the entitlement verification key is absent.

See [Security](docs/security.md) and [Protocol](docs/protocol.md).

## HACS release status

The directory structure follows HACS custom-integration requirements, and CI
includes HACS and Hassfest validation. HACS requires the repository to be public
before it can be installed. This repository will remain private until the
maintainer explicitly approves release.

## License

MIT

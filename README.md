# Shift + for Home Assistant

<p align="center"><img src="docs/images/shift-plus-icon.png" width="180" alt="Shift +"></p>
<h3 align="center">Bring your roster into Home Assistant</h3>

The official Home Assistant companion integration for the [Shift + Android app](https://play.google.com/store/apps/details?id=ie.shiftplus.app), maintained by **GIBBO**.

Shift + 5.1.0 synchronizes roster configuration, annual leave and overtime from Android, calculates schedule projections locally in Home Assistant, and exposes them for dashboards and automations. Synchronization requires **Shift + Premium**.

## Features

- Current Shift, Next Shift and Next Shift Date
- Early, Late, Night and Rest duty calculation
- Rostered and effective start/end times
- Next Book On, Next Book Off and booking windows
- Working now, today and tomorrow binary sensors
- Active roster and unit details
- Roster, annual-leave and overtime calendars
- Leave taken, planned and remaining
- Previous, current and next 28-day overtime totals
- Manual sync and secure pairing controls
- Compatibility summary sensors retained from public 5.0.1

Android synchronizes configuration and records. Home Assistant stores that replica and recalculates time-sensitive schedule values every minute. Overtime can extend working boundaries, Rest-day overtime can create them, and applicable partial leave can suppress a book-on or book-off boundary.

## Requirements

- Home Assistant 2024.7.0 or newer
- HACS
- [Shift + for Android](https://play.google.com/store/apps/details?id=ie.shiftplus.app)
- Active Shift + Premium
- Network access from Android to Home Assistant

## Install through HACS

1. In HACS, add `https://github.com/bgibbo/shift-plus-home-assistant` as an **Integration** custom repository.
2. Download **Shift +** and restart Home Assistant.
3. Open **Settings → Devices & services → Add integration** and add **Shift +**.
4. Press **Create Android pairing QR** on the Shift + device.
5. Scan the QR in the Shift + Android app and allow the initial synchronization to finish.

The QR is single-use and expires after five minutes.

> **Screenshot safety:** never share a live pairing QR. It contains short-lived pairing credentials.

## Entities and dashboards

The complete [entity reference](docs/entities.md) identifies synchronized and locally calculated values. Ready-to-use examples are in the [dashboard guide](docs/dashboard.md).

Public 5.0.1 summary IDs are retained where practical so existing dashboards continue working. The 5.1.0 migration also preserves compatible pairing credentials and synchronized replica records from both public 5.0.1 and the earlier feature-rich 5.0.1 implementation.

## Synchronization and security

Pairing uses a short-lived QR, production three-part EdDSA JWT verification, X25519 key agreement and HKDF-SHA256. Requests use HMAC-SHA256 with nonce replay protection. Premium grants are bound to the HA entry, session, installation, device and app public key; renewal rejects stale grants and entitlement identity changes.

See the [protocol](docs/protocol.md) and [security model](docs/security.md) for details.

## Troubleshooting

- **QR rejected or expired:** create a new QR and scan it within five minutes.
- **Pairing unavailable:** confirm Premium is active and the phone can reach Home Assistant.
- **Schedule is wrong:** confirm the active roster, unit and schedule settings in Android, then synchronize.
- **Sync stopped:** check Last successful sync and Android pairing status, then confirm Premium renewal succeeds.
- **Calendar is empty:** open Shift + briefly and allow synchronization to complete.

Never include purchase tokens, pairing QR codes, HA access tokens, credentials, private URLs or personal roster data in a support report. Use the [GitHub issue tracker](https://github.com/bgibbo/shift-plus-home-assistant/issues).

## Screenshots

Genuine sanitized screenshots are still required. Follow the [screenshot checklist](docs/images/README.md); do not capture a live QR or personal data.

## Development

Contributor setup and validation commands are in [docs/development.md](docs/development.md). The project is maintained by **GIBBO** and licensed under the [MIT License](LICENSE).

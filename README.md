# Shift + for Home Assistant

<p align="center">
  <img src="docs/images/shift-plus-icon.png" width="160" alt="Shift + icon">
</p>

Bring your Shift + roster into Home Assistant.

View synchronized roster configuration, annual leave, overtime and connection
status from a dedicated Shift + dashboard, and use that information in Home
Assistant automations. Shift + is primarily an Android shift-roster app; this is
its official Home Assistant companion integration.

> **Development status:** this repository is currently private and has not been
> released or submitted to HACS. The instructions below describe the intended
> user experience and private testing workflow. Do not treat it as publicly
> available software yet.

## What is Shift +?

Shift + is an Android application for planning rotating rosters, viewing daily
duties, recording annual leave and tracking overtime. The Android app remains the
source of truth for roster setup and phone-side editing.

## What does the integration do?

The integration pairs locally with the Android app, receives supported Shift +
records, and exposes dashboard-safe Home Assistant sensors. Synchronization is
incremental and bidirectional for supported records. Device requests are
authenticated and pairing requires a genuine Shift + Premium entitlement.

The current protocol supplies active roster/unit identifiers, annual leave and
overtime. Computed daily E/L/N/R duties are not yet transferred, so the project
does not claim to expose today's or the next duty until that protocol work is
complete.

## Screenshots

Final release screenshots are awaiting the sanitized end-to-end Home Assistant
test. The planned Android roster, Home Assistant dashboard, roster-card and
pairing images are tracked in [`docs/images`](docs/images/README.md). No mock or
fabricated product screenshots are used.

## Features

- Guided, five-minute QR pairing from an authenticated Home Assistant page
- X25519/HKDF device credential establishment
- Replay-resistant HMAC authentication for sync requests
- Signed Premium entitlement verification using only the public Ed25519 key
- Active roster and unit sensor
- Annual-leave and overtime sensors
- Sanitized monthly calendar event data
- Pairing, sync and Premium-status sensor without entitlement details
- Built-in-card dashboard for maximum compatibility
- Responsive, dependency-free Shift + monthly roster card
- Light and dark Home Assistant theme support
- Incremental synchronization and deterministic conflict handling

## Requirements

- Home Assistant with support for custom integrations
- Shift + installed on Android
- Shift + Premium purchased through Google Play
- A network route from the Android device to Home Assistant
- The production entitlement service and verification key configured

## Intended installation journey

1. Install Shift + on Android.
2. Set up your roster in Shift +.
3. Install **Shift + for Home Assistant** through HACS once it is publicly
   released. Private testers must install the integration manually.
4. Add the Shift + integration under **Settings → Devices & services**.
5. Complete pairing from the Android app.
6. Add the supplied Shift + dashboard to the Home Assistant sidebar.
7. Optionally use Shift + entities in automations.

### Private development installation

Copy `custom_components/shift_plus` into Home Assistant's `custom_components`
directory and restart Home Assistant. Add **Shift +** under **Settings → Devices
& services** and enter the production entitlement public verification key. This
manual route is only for authorized private testing.

## Pairing

1. In Home Assistant, run the `shift_plus.create_pairing` action.
2. Open the resulting persistent notification while signed in.
3. In Shift + on Android, open **Home Assistant** and scan the QR code.
4. The QR expires after five minutes and can be used only once.

Pairing is a Shift + Premium feature. The app verifies the Google Play purchase
with the private entitlement backend. Home Assistant independently verifies the
short-lived, pairing-bound entitlement signature and claims.

## Shift + dashboard

Two ready-made configurations are included:

- [`lovelace/shift-plus-dashboard.yaml`](lovelace/shift-plus-dashboard.yaml)
  uses built-in Home Assistant cards only.
- [`lovelace/shift-plus-custom-card-dashboard.yaml`](lovelace/shift-plus-custom-card-dashboard.yaml)
  uses the supplied Shift + roster card for a more app-like monthly view.

See the [dashboard guide](docs/dashboard.md) for sidebar and resource setup.

## Available entities

The integration creates paired-device, active-roster, calendar, annual-leave and
overtime sensors. See the complete [entity inventory](docs/entities.md) for
states, attributes, availability, dashboard use and automation suitability.

Entity output deliberately excludes purchase and entitlement tokens, device
credentials, pairing secrets, record IDs, free-text notes and cryptographic
material.

## Example automations

[`docs/automations.yaml`](docs/automations.yaml) includes examples for:

- an annual-leave reminder;
- synchronization attention;
- an increased overtime total; and
- alternate morning behaviour on a leave day.

Duty-specific Early/Late/Night/Rest examples will be added only when computed
daily duty entities genuinely exist.

## Troubleshooting

- **No entities:** restart Home Assistant after copying the integration and
  confirm the config entry loaded successfully.
- **Pairing unavailable:** configure the entitlement public key and confirm
  Shift + Premium is active in the Android app.
- **QR rejected:** create a new pairing notification; codes expire after five
  minutes and are single use.
- **Calendar empty:** open Shift + and synchronize. Only leave and overtime are
  currently available as dated calendar events.
- **Custom card missing:** add its JavaScript-module resource and hard-refresh
  the browser as described in the dashboard guide.
- **Sync stopped:** check the paired-device sensor and restore the Google Play
  purchase in Shift +. Expired or revoked entitlement prevents synchronization.

## Privacy and security

Shift + data remains between the paired Android app and Home Assistant during
normal synchronization. The entitlement backend receives the Google Play
purchase proof and pairing bindings needed to issue a short-lived entitlement.

The repository contains no private signing key, Google credential, purchase
token, HMAC credential or production secret. See the [security model](docs/security.md)
and [protocol](docs/protocol.md) for technical details.

## Current release status

This is private release-preparation work. Before any public release it still
requires real-device entitlement testing, fresh-user/fresh-Home-Assistant
testing, duty-data protocol completion, sanitized screenshots, supported-version
testing, Hassfest/HACS validation and explicit maintainer approval.

No public HACS submission or tagged release exists.

## Development

Contributor setup and validation commands are documented in
[`docs/development.md`](docs/development.md). The project is licensed under the
[MIT License](LICENSE).

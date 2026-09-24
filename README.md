# Shift + for Home Assistant

<p align="center">
  <img src="docs/images/shift-plus-icon.png" width="160" alt="Shift + icon">
</p>

Bring your Shift + roster into Home Assistant. Shift + is an Android app for
planning rotating rosters, viewing daily duties, recording annual leave and
tracking overtime. This official companion integration exposes synchronized
Shift + information to Home Assistant dashboards and automations.

Home Assistant synchronization is a **Shift + Premium** feature.

## What the integration provides

- Secure QR pairing between Shift + and Home Assistant
- Automatic synchronization of supported roster information
- Active-roster and unit information
- Annual-leave and overtime sensors
- Sanitized calendar event data
- Pairing, synchronization and Premium-status information
- Ready-made Home Assistant dashboards and a responsive Shift + roster card

The Android app remains the source of truth for roster setup and phone-side
editing. The current protocol synchronizes active roster/unit identifiers,
annual leave and overtime. Computed daily E/L/N/R duties are not currently
transferred to Home Assistant.

## Prerequisites

- Home Assistant 2024.7.0 or newer
- [HACS](https://www.hacs.xyz/) installed and configured
- Shift + installed on an Android device
- An active Shift + Premium purchase through Google Play
- Network access from the Android device to Home Assistant

## Install through HACS as a custom repository

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu and select **Custom repositories**.
3. Enter this repository URL:
   `https://github.com/bgibbo/shift-plus-home-assistant`
4. Select **Integration** as the repository type and choose **Add**.
5. Find **Shift +** in HACS and choose **Download**.
6. Restart Home Assistant when HACS prompts you, or restart it from
   **Settings → System → Restart Home Assistant**.

After the restart, open **Settings → Devices & services → Add integration**,
search for **Shift +**, and complete the setup form.

## Pair with the Shift + Android app

1. In Home Assistant, open **Developer Tools → Actions**.
2. Run the **Shift +: Create pairing QR** action
   (`shift_plus.create_pairing`).
3. Open the persistent notification created by Home Assistant. It contains a
   pairing QR code that expires after five minutes and can be used once.
4. In the Shift + Android app, open **Home Assistant**, start pairing, and scan
   the QR code.
5. Wait for Shift + to confirm that pairing and the initial synchronization
   completed.

Pairing requires an active Shift + Premium entitlement. Shift + verifies the
purchase and Home Assistant validates the short-lived pairing authorization.
No purchase token or private signing material is stored in this repository.

## Entities

The integration creates these sensors on the **Shift +** device:

- **Paired devices** — connection, synchronization and Premium status
- **Active roster** — active roster and unit identifiers
- **Calendar** — sanitized annual-leave and overtime events
- **Annual leave** — synchronized leave totals and upcoming leave
- **Overtime** — synchronized hours, entry count and upcoming overtime

Home Assistant may add a suffix if an entity ID is already in use. See the
[complete entity reference](docs/entities.md) for states and attributes.

## Synchronization and Premium renewal

After pairing, Shift + synchronizes supported changes automatically. Premium
authorization is renewed securely in the background while the Google Play
purchase remains active. If Premium expires, is cancelled or cannot be renewed,
synchronization stops when the current authorization expires and resumes after
Premium access is restored and renewed.

## Dashboards

Two example dashboards are included:

- [`lovelace/shift-plus-dashboard.yaml`](lovelace/shift-plus-dashboard.yaml)
  uses built-in Home Assistant cards.
- [`lovelace/shift-plus-custom-card-dashboard.yaml`](lovelace/shift-plus-custom-card-dashboard.yaml)
  uses the supplied Shift + roster card.

See the [dashboard guide](docs/dashboard.md) for setup and resource instructions.

## Updating

Open **HACS → Shift +** when an update is available, download the new version,
and restart Home Assistant if prompted. Existing pairing data is retained during
normal HACS updates.

## Unpairing and re-pairing

To replace an existing connection, remove the Shift + integration entry from
**Settings → Devices & services**, then add **Shift +** again and create a new
pairing QR. In the Android app, remove the old Home Assistant connection if it
is still listed, then scan the new QR. A new pairing creates fresh device
credentials; old QR codes and credentials cannot be reused.

## Troubleshooting

- **Shift + is missing from Add integration:** confirm HACS downloaded the
  integration, then restart Home Assistant and refresh the browser.
- **Pairing is unavailable:** confirm Shift + Premium is active in the Android
  app and that the phone can reach Home Assistant over the network.
- **QR rejected or expired:** create a new pairing QR. Codes expire after five
  minutes and are single use.
- **Initial sync does not complete:** keep Shift + open briefly, confirm the
  phone can reach Home Assistant, and retry with a new pairing QR.
- **Calendar is empty:** open Shift + and allow synchronization to complete.
  The current calendar sensor contains annual leave and overtime events.
- **Custom card is missing:** add its JavaScript-module resource and hard-refresh
  the browser as described in the dashboard guide.
- **Sync stopped:** check the paired-devices sensor and confirm Premium remains
  active in Shift +. If necessary, restore the purchase and re-pair.

For reproducible problems, open an issue in the
[GitHub issue tracker](https://github.com/bgibbo/shift-plus-home-assistant/issues).
Do not include purchase tokens, QR codes, Home Assistant access tokens, device
credentials, private URLs or personal roster data in an issue.

## Privacy and security

Normal synchronization occurs directly between the paired Android app and Home
Assistant. Pairing uses short-lived authorization, authenticated requests and
single-use QR codes. Entities exclude purchase and entitlement tokens, device
credentials, pairing secrets, free-text notes and cryptographic material.

Technical details are available in the [security model](docs/security.md) and
[protocol documentation](docs/protocol.md).

## Development

Contributor setup and validation commands are documented in
[`docs/development.md`](docs/development.md). The project is licensed under the
[MIT License](LICENSE).

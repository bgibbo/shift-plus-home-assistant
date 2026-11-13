# Shift + for Home Assistant

<p align="center"><img src="docs/images/shift-plus-icon.png" width="150" alt="Shift + app icon"></p>

<p align="center"><a href="https://www.shiftplus.plus/"><img src="docs/images/shift-plus-promotional.png" alt="Official Shift + roster manager promotional artwork"></a></p>

Bring the roster you already manage in **Shift + for Android** into Home Assistant. After a secure one-time pairing, Shift + keeps your active roster, annual leave and overtime in sync so Home Assistant can show your schedule alongside the rest of your day.

The public release remains **v5.1.2**. This audit branch contains unreleased documentation and dashboard work; it does not represent a published v5.1.3 release.

## Why use it?

- See your current and next duty, active roster and unit at a glance.
- See rostered and effective start/end times, including Book On and Book Off windows.
- Track leave, overtime, working status and calendars in Home Assistant.
- Add a responsive monthly roster card with Android-matched Early, Late, Night and Rest colours, leave/overtime markers and a current-day outline.
- Browse calculated historical and future months without exposing private pairing or entitlement data to the card.

Shift + Premium is required for Android pairing and roster synchronization. Home Assistant receives a local synchronized copy and calculates its live schedule information locally. See the [security model](docs/security.md) for technical details.

> The artwork above is official Shift + promotional artwork, not a Home Assistant screenshot. A reviewed, sanitised dashboard screenshot has not yet been supplied for publication; this repository deliberately does not use a mock or AI-generated substitute.

## Requirements

- Home Assistant 2024.7.0 or newer
- [Shift + for Android](https://play.google.com/store/apps/details?id=ie.shiftplus.app)
- An active Shift + Premium subscription
- Android and Home Assistant able to reach one another for pairing and sync

On Home Assistant 2026.11 and newer, community integrations are installed from **Settings → Marketplace**. Older installations use **HACS → Integrations**. When Shift + is available in the default catalogue, install it there; catalogue users do not need to add this repository manually.

## Quick start

1. Install **Shift +** from Marketplace or HACS, then follow any restart prompt.
2. Go to **Settings → Devices & services → Add integration** and select **Shift +**.
3. Create an Android pairing QR from the Shift + device, then scan it in the Shift + Android app within five minutes.
4. Wait for the first sync and confirm the Shift + entities are populated.
5. Add the optional monthly card to a dashboard with the YAML below.

```yaml
type: custom:shift-plus-roster-card
title: Shift + roster
calendar_entity: sensor.shift_calendar
roster_entity: sensor.shift_active_roster
status_entity: sensor.shift_paired_devices
leave_entity: sensor.shift_annual_leave
overtime_entity: sensor.shift_overtime
font_size: medium
calendar_cell_size: comfortable
layout_density: comfortable
```

For normal storage-mode dashboards, the integration registers the JavaScript resource automatically. You do not need to copy a `lovelace` folder, edit `.storage`, use a terminal, or add a resource manually in the normal path.

## Guides and support

- [Beginner installation and pairing guide](docs/installation.md)
- [Monthly roster card and appearance guide](docs/dashboard.md)
- [Entity reference](docs/entities.md)
- [Troubleshooting](docs/installation.md#troubleshooting)
- [Security model](docs/security.md)
- [Report an issue](https://github.com/bgibbo/shift-plus-home-assistant/issues)

Do not include pairing QR codes, credentials, URLs, device IDs, purchase information, personal roster data or private notes in screenshots or support requests.

## Development

Contributor setup and validation commands are in [docs/development.md](docs/development.md). The project is maintained by **GIBBO** and licensed under the [MIT License](LICENSE).

# Shift + for Home Assistant

<p align="center"><img src="docs/images/shift-plus-icon.png" width="150" alt="Shift + app icon"></p>

<p align="center"><a href="https://www.shiftplus.plus/"><img src="docs/images/shift-plus-promotional.png" alt="Shift + roster manager promotional artwork"></a></p>

Bring your Shift + roster into Home Assistant. Shift + securely synchronizes your active roster, annual leave and overtime from the Android app, then calculates live duty, booking-window and schedule information locally in Home Assistant.

> A genuine, sanitised monthly-roster dashboard screenshot will be added here when the developer-supplied capture has passed review. The promotional artwork above is official artwork, not a Home Assistant screenshot.

## What you get

- Current and next shift, roster day, and active roster/unit
- Rostered and effective start/end times, including Book On and Book Off windows
- Working-now/today/tomorrow status, roster/leave/overtime calendars, leave totals, and 28-day overtime totals
- A responsive monthly roster card with duty colours, leave/overtime markers, current-date highlighting, and adjustable presentation
- Secure Android pairing and automatic ongoing synchronisation

Shift + Premium is required to pair the Android app and synchronize roster data. Home Assistant keeps a local synchronized replica and calculates time-sensitive schedule values locally.

## Requirements and compatibility

- Home Assistant 2024.7.0 or newer
- [HACS](https://www.hacs.xyz/)
- [Shift + for Android](https://play.google.com/store/apps/details?id=ie.shiftplus.app)
- Active Shift + Premium
- Network access from the Android device to the Home Assistant instance

## Install and pair

Install through **HACS → Integrations**, then restart Home Assistant when HACS asks. Add **Shift +** under **Settings → Devices & services → Add integration**, create the Android pairing QR, and scan it in the Shift + Android app. Allow the first synchronization to finish before building dashboards.

The complete beginner-friendly instructions, including initial sync checks and the custom-card setup, are in the [installation guide](docs/installation.md). The pairing QR is single-use and expires after five minutes; never include it in a screenshot or support request.

## Dashboard

Home Assistant's built-in entity and calendar cards work with Shift + immediately. For the optional monthly roster card, create a test or personal dashboard, choose **Manual** in the card editor, and paste:

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

Storage-mode dashboards register the required JavaScript resource automatically. See the [dashboard guide](docs/dashboard.md) for presentation options, YAML-mode configuration, colour/marker meanings, and troubleshooting.

## Help and support

- [Installation guide](docs/installation.md)
- [Dashboard guide](docs/dashboard.md)
- [Entity reference](docs/entities.md)
- [Troubleshooting](docs/installation.md#troubleshooting)
- [Security model](docs/security.md)
- [GitHub issues](https://github.com/bgibbo/shift-plus-home-assistant/issues)

When seeking help, remove pairing QR codes, credentials, URLs, device IDs, purchase information, private roster data, and personal information.

## Development

Contributor setup and validation commands are in [docs/development.md](docs/development.md). The project is maintained by **GIBBO** and licensed under the [MIT License](LICENSE).

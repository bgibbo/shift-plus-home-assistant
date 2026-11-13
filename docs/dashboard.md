# Shift + dashboards

Shift + works with ordinary Home Assistant entity and calendar cards as soon as the first Android synchronization completes. It also provides an optional monthly roster card for a quick, Android-aligned view of the active schedule.

## Monthly roster card

For a normal storage-mode dashboard, install Shift + through Marketplace or HACS, then add a **Manual** card. The integration registers its JavaScript module automatically; no copied `lovelace` folder or manually maintained resource is needed.

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

Use the entity picker if your instance has chosen suffixed entity IDs. Existing public 5.0.1 summary sensors remain available for older dashboards.

### Reading the card

- **Early** duties use green, **Late** light blue, **Night** dark blue and **Rest** pink, matching the Shift + Android calendar.
- A green briefcase is annual leave; a dark right-half overlay is overtime.
- The red outline is today.
- The arrows browse calculated historical and future months. The card requests only one authenticated, bounded month from Home Assistant when the visible month is outside the initial sync window.
- The synchronization line is a quick status indicator; it is not a substitute for resolving any integration error shown on the device page.

Only duty codes and marker dates are provided to the card. Pairing material, entitlement data, record descriptions and notes are not exposed to it.

### Presentation options

The default is designed to remain readable across phones, tablets and desktops. The following options affect appearance only:

| Option | Values | Default |
|---|---|---|
| `font_size` | `small`, `medium`, `large` | `medium` |
| `calendar_cell_size` | `compact`, `comfortable`, `spacious` | `comfortable` |
| `layout_density` | `compact`, `comfortable`, `spacious` | `comfortable` |

Long active-roster names wrap instead of being silently truncated. Keep duty colours readable and avoid setting every option to its most compact value on a small screen.

## YAML-mode dashboards

Most users do not need YAML-mode Lovelace. If you maintain a YAML dashboard, declare the versioned JavaScript module using the version URL supplied by the installed integration release, then use the same card YAML above. Do not copy the example `lovelace` directory wholesale or edit Home Assistant's `.storage` files.

## Suggested dashboard layout

1. Current Shift, Next Shift and Next Shift Date.
2. Next Book On and Next Book Off.
3. Working now/today/tomorrow.
4. Active roster and unit.
5. Leave taken/planned/remaining.
6. Previous/current/next 28-day overtime.
7. Roster, annual-leave and overtime calendars.
8. Last successful sync and pairing status in a diagnostic section.

## Screenshots

Only publish genuine, sanitised Home Assistant screenshots. The approved promotional artwork in the README is not a dashboard capture. The exact required dashboard captures and sanitisation checklist are in [docs/images/README.md](images/README.md).

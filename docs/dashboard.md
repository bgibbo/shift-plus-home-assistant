# Dashboard guide

Shift + supports built-in Home Assistant cards for current and next duty, book-on/off, working status, leave, overtime and calendars. It also includes an optional Shift + monthly roster card.

Use entity selection in the dashboard editor after installation because Home Assistant may suffix an entity ID that is already occupied. Existing public 5.0.1 summary sensors remain available for older dashboards.

The examples in `lovelace/` can be copied into a manual dashboard. Review every entity ID before saving.

## Shift + monthly roster card

For normal Home Assistant storage-mode dashboards, the integration registers the
card resource automatically. Reload the browser once after installing or
updating the integration, then copy
`lovelace/shift-plus-custom-card-dashboard.yaml` into a manual dashboard.

For YAML-mode Lovelace, add this resource to your existing dashboard
configuration before using the card:

```yaml
resources:
  - url: /shift_plus/shift-plus-roster-card.js
    type: module
```

The card reads the existing **Calendar** compatibility sensor. It receives only
the active roster's duty code and leave/overtime marker dates for a bounded
rolling window; it does not expose pairing, entitlement, notes, or record
descriptions. It shows an unavailable state until initial Android sync has
completed.

### Optional card presentation

The card is responsive by default: compact on phones, balanced on tablets, and
comfortable on desktop displays. It preserves readable duty colours and lets a
long active-roster name wrap rather than truncating it. The following optional
configuration values tune presentation only; they do not affect roster data or
synchronization:

```yaml
type: custom:shift-plus-roster-card
font_size: large # small, medium (default), large
calendar_cell_size: spacious # compact, comfortable (default), spacious
layout_density: compact # compact, comfortable (default), spacious
```

## Suggested layout

1. Current Shift, Next Shift and Next Shift Date.
2. Next Book On and Next Book Off.
3. Working now/today/tomorrow.
4. Active roster and unit.
5. Leave taken/planned/remaining.
6. Previous/current/next 28-day overtime.
7. Roster, annual-leave and overtime calendars.
8. Last successful sync and pairing status in a diagnostic section.

## Screenshots

Only publish genuine sanitized Home Assistant screenshots. Follow `docs/images/README.md`. Never show a pairing QR, private URL, device identifier, personal notes, entitlement data or credential material.

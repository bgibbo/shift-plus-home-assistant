# Dashboard guide

Shift + 5.1.0 supports built-in Home Assistant cards for current and next duty, book-on/off, working status, leave, overtime and calendars.

Use entity selection in the dashboard editor after installation because Home Assistant may suffix an entity ID that is already occupied. Existing public 5.0.1 summary sensors remain available for older dashboards.

The examples in `lovelace/` can be copied into a manual dashboard. Review every entity ID before saving.

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

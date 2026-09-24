# Entity inventory

Entity IDs below are defaults; Home Assistant may suffix or users may rename
them. All entities belong to the **Shift +** device and update after sync.

| Entity | Default ID | State | Attributes | Dashboard | Automation | Availability |
|---|---|---|---|---|---|---|
| Paired devices | `sensor.shift_paired_devices` | Paired-device count | `sync_status`, `premium_status`, server cursor, stored-record count, pairing path | Yes | Yes | Available after integration startup |
| Active roster | `sensor.shift_active_roster` | Active roster ID or `unknown` | Roster and unit IDs | Yes | Yes | Available; `unknown` before configuration sync |
| Calendar | `sensor.shift_calendar` | Sanitized calendar-event count | Leave/overtime `events`; duty-data capability flag | Custom card | Yes | Available; empty before sync |
| Annual leave | `sensor.shift_annual_leave` | Total synchronized leave days | Whether today is leave and next leave date | Yes | Yes | Available; zero before leave sync |
| Overtime | `sensor.shift_overtime` | Total synchronized overtime hours | Entry count and next overtime date | Yes | Yes | Available; zero before overtime sync |

Calendar events exclude record IDs, operation IDs, organisation names and free
text descriptions. No purchase token, entitlement token, signing key, pairing
secret, device credential or HMAC material is exposed by an entity.

## Current protocol boundary

The app currently synchronizes active roster/unit identifiers, annual leave and
overtime. It does not synchronize the computed duty for each date. Consequently,
there are no truthful **today's duty**, **next duty**, or **upcoming duties**
entities yet. The card visibly reports that boundary and is ready to consume a
future sanitized `days` attribute without changing its visual design.

Current Shift, Next Shift and book-on/book-off information displayed in the
Shift + Android app is calculated and presented by the app. Those values are not
entities in the released Home Assistant 5.0.1 integration.

# Entity reference

Shift + 5.1.0 exposes the following entities. Home Assistant may add a suffix when an entity ID is already occupied.

## Schedule sensors

| Name | Source |
|---|---|
| Current Shift | Calculated locally from date, active roster, unit and schedule overrides |
| Next Shift | Calculated locally by scanning forward |
| Next Shift Date | Date of the locally calculated next working duty |
| Roster day | Local roster-cycle position |
| Active roster / Active unit | Synchronized Android configuration |
| Rostered start / end | Local roster calculation |
| Effective start / end | Local roster plus overtime, briefing and leave rules |
| Next Book On / Next Book Off | Locally calculated next effective boundaries |
| Booking on/off opens/closes | Local windows before effective boundaries |

## Leave and overtime sensors

- Previous, current and next 28-day overtime totals are calculated from synchronized overtime records.
- Leave taken, planned and remaining are calculated from synchronized leave records and local roster definitions.
- Last successful sync, Unacknowledged Home Assistant changes, Journal entries
  awaiting acknowledgement and Sync conflicts are diagnostic entities.

## Binary sensors

Working now, Working today, Working tomorrow, Annual leave today, Overtime today, and Android app paired.

## Calendars

Roster is calculated locally. Annual leave and Overtime calendars are generated from synchronized records.

## Controls

Refresh schedule recalculates HA's local schedule. Android synchronization
occurs when Shift + next connects. Create Android pairing QR creates a
five-minute single-use QR. Android pairing QR is unavailable when no live QR
exists, including after successful pairing. Android pairing status should show
`paired` for an existing active pairing.

Sync conflicts exposes a sanitized `unresolved` list. Choose one conflict ID
and run `shift_plus.resolve_conflict` with `selection: current` or
`selection: alternative`. The action resolves only that conflict and queues the
merged record for the next Android-initiated synchronization.

## Compatibility sensors

The public 5.0.1 unique IDs for Paired devices, Active roster, Calendar, Annual leave and Overtime remain available. This prevents avoidable dashboard and automation breakage during upgrade.

## Data boundary

Android supplies active configuration, roster and unit IDs, schedule settings, annual-leave records and overtime records. Home Assistant supplies no competing roster dataset: it stores the synchronized replica and derives HA-facing schedule projections from the bundled roster contract.

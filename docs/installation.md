# Install and pair Shift +

This guide uses Home Assistant's normal interface. A catalogue installation does not require copying files, adding a custom repository, using a terminal, or editing Home Assistant storage.

## Before you begin

You need:

- Home Assistant 2024.7.0 or newer.
- Shift + for Android with active Shift + Premium.
- An Android device that can reach your Home Assistant instance.
- A Home Assistant administrator account.

Pairing is a one-time secure link between the Android app and this Home Assistant instance. The QR code is single-use and expires after five minutes. Never share or screenshot it.

## Install from Home Assistant Marketplace

Home Assistant 2026.11 and newer include Marketplace under **Settings → Marketplace**.

1. Open **Settings → Marketplace**.
2. Search for **Shift +** and open its integration page.
3. Select **Install** and review the version offered.
4. If setup does not open automatically, go to **Settings → Devices & services** and select **Add integration**, then search for **Shift +**.

Marketplace content is community-maintained rather than part of Home Assistant Core. Install only the public Shift + repository you expect. If Shift + is already shown in Marketplace, do not add it again as a custom repository.

## Install with HACS (older Home Assistant installations)

On Home Assistant versions before Marketplace, use HACS if it is already installed:

1. Open **HACS** in the sidebar and select **Integrations**.
2. Select **Explore & download repositories**, search for **Shift +**, and open the result.
3. Select **Download** and confirm the offered version.
4. Restart Home Assistant only if HACS asks you to: **Settings → System → Restart Home Assistant**.
5. Go to **Settings → Devices & services → Add integration**, then search for **Shift +**.

Shift + is in the Marketplace/HACS default catalogue. If it does not appear immediately, allow the catalogue to refresh before retrying. Do not add a custom repository for the normal public installation.

## Pair Android and perform the first sync

1. Complete the Shift + integration setup in **Settings → Devices & services**.
2. Open the created Shift + device and select **Create Android pairing QR**.
3. In Shift + on Android, open the Home Assistant pairing flow and scan the QR within five minutes.
4. Keep both devices online until Android reports success and Home Assistant shows a paired state.
5. Wait for the initial synchronization to finish.

Then open the Shift + device page and check that **Last successful sync** is recent and that Current Shift, Next Shift, Active roster, Active unit, Annual leave, Overtime, and the calendar entities have values. Android initiates the synchronization; Home Assistant does not need a separate import step.

## Add the monthly roster card

After the initial sync:

1. Open the dashboard where you want the card.
2. Select **Edit dashboard → Add card → Manual**.
3. Paste the following YAML, checking entity IDs with the entity picker if Home Assistant has added a suffix.
4. Save the card.

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

The resource is registered automatically for normal storage-mode dashboards. The card uses Android-matched duty colours: Early is green, Late is light blue, Night is dark blue, and Rest is pink. The green briefcase marks annual leave, the dark right-half overlay marks overtime, and the red outline marks today. Use the arrows to browse calculated historical and future months.

`font_size` accepts `small`, `medium` and `large`; `calendar_cell_size` and `layout_density` each accept `compact`, `comfortable` and `spacious`. These options affect presentation only, not your roster or synchronization.

## Updating

Install updates through **Settings → Updates** on Marketplace systems or from the integration page in HACS. Restart Home Assistant if prompted, then refresh your browser. The card resource URL is versioned automatically for newly registered resources so browser caches do not retain an older card after an upgrade.

## Troubleshooting

### The card is unavailable or has no duty colours

Confirm pairing and the first Android synchronization have completed. Check that the configured Calendar entity has values, then refresh the browser. The card intentionally has no roster data before its first successful sync.

### A historical or future month cannot load

The card asks Home Assistant for one authenticated, bounded month at a time. Check the card's visible error message, confirm the integration is loaded, and refresh after an update. If the error persists, include the month and error text in an issue, but omit QR codes, addresses, device IDs and roster details.

### The custom card is not recognised after an update

First perform a full browser refresh. Normal storage-mode dashboards register the resource automatically. As a fallback, an administrator can open **Settings → Dashboards → Resources**, inspect the existing Shift + JavaScript module resource, and ensure its URL includes the versioned URL supplied by the installed integration's release notes. Do not create duplicate resources and do not edit `.storage`.

### Pairing or synchronization does not finish

Confirm Premium is active, the Android device can reach Home Assistant, and the QR has not expired. Create a new QR when needed, but never expose it in a support request. See the [security model](security.md) for the high-level pairing design.

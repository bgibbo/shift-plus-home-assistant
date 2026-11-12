# Install Shift + with HACS

This guide uses Home Assistant's normal interface. It does not require copying files, command-line commands, or editing Home Assistant storage.

## Before you begin

You need Home Assistant 2024.7.0 or newer, HACS, the Shift + Android app with an active Premium subscription, and a phone that can reach your Home Assistant instance.

## 1. Install from HACS

1. Open **HACS** in Home Assistant's sidebar.
2. Select **Integrations**.
3. Select **Explore & download repositories** and search for **Shift +**.
4. Open **Shift +**, select **Download**, and confirm the version offered by HACS.
5. Restart when HACS requests it: **Settings → System → Restart Home Assistant**.

If Shift + is not visible, let HACS refresh its catalogue and confirm Home Assistant meets the requirement. A development branch is not the normal public installation method.

## 2. Add Shift + and pair Android

1. Go to **Settings → Devices & services**.
2. Select **Add integration**, search for **Shift +**, and complete setup.
3. Open the created Shift + device and select **Create Android pairing QR**.
4. In Shift + on Android, open its Home Assistant pairing flow and scan the QR within five minutes.
5. Keep both apps open until Android completes and Home Assistant shows the paired state.

The QR is single-use. Never share, screenshot, or publish it.

## 3. Confirm the first synchronization

Android initiates synchronization when it connects to Home Assistant. After it finishes, open the Shift + device page and confirm **Last successful sync** is recent and schedule entities are populated. Check Current Shift, Next Shift, Active roster, Active unit, Annual leave, Overtime, and the roster/leave/overtime calendars.

If values are not present yet, open Shift + on Android, confirm its network access, and allow its normal synchronization to complete.

## 4. Create a Shift + dashboard

1. Go to **Settings → Dashboards** and create or edit a personal dashboard.
2. Add Home Assistant entity or calendar cards using Shift + entities.
3. For the monthly card, choose **Add card → Manual** and paste:

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

Home Assistant may suffix entity IDs if an ID is already in use. Confirm the IDs with the entity picker before saving.

### Card appearance

The default layout is compact on phones, balanced on tablets, and comfortable on desktop displays. These presentation-only options are available:

| Option | Values | Default |
|---|---|---|
| `font_size` | `small`, `medium`, `large` | `medium` |
| `calendar_cell_size` | `compact`, `comfortable`, `spacious` | `comfortable` |
| `layout_density` | `compact`, `comfortable`, `spacious` | `comfortable` |

Duty backgrounds identify configured Early, Late, Night and Rest duties. Yellow marks annual leave, purple marks overtime, the blue outline marks today, and the sync line reflects current integration synchronization status.

## Troubleshooting

### The monthly card is unavailable

Complete Android pairing and wait for initial synchronization, then refresh the browser. The card intentionally has no roster data before the first sync.

### The custom card is not recognised

Storage-mode dashboards register the resource automatically. If it is not recognised after restarting Home Assistant and refreshing the browser:

1. Open **Settings → Dashboards → Resources**.
2. Select **Add Resource**.
3. Set URL to `/shift_plus/shift-plus-roster-card.js`.
4. Set type to **JavaScript module**.
5. Save and refresh the browser.

For YAML-mode Lovelace, see the [dashboard guide](dashboard.md#shift--monthly-roster-card).

### Pairing or synchronization does not finish

Confirm Premium is active, the phone can reach Home Assistant, and the QR has not expired. Create a new QR if needed, but never expose it in a support request.

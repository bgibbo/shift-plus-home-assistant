# Shift + dashboard

The repository includes two dashboard choices. Entity IDs are user-editable in
Home Assistant, so confirm them under **Settings → Devices & services →
Entities** before pasting either example.

## What the examples show

| Example | Included views |
|---|---|
| Built-in cards | Active roster ID, paired-device and sync status, calendar-record count, annual-leave and overtime totals, next leave date and recent activity |
| Shift + roster card | A responsive monthly calendar of synchronized annual-leave and overtime events, plus roster, connection and summary information |

Version 5.0.1 does not supply computed daily duties to Home Assistant. Current
Shift, Next Shift and book-on/book-off information remain Android-app features.
The dashboard examples therefore do not claim or simulate those entities.

## Built-in Home Assistant dashboard

[`lovelace/shift-plus-dashboard.yaml`](../lovelace/shift-plus-dashboard.yaml)
uses only built-in cards.

1. Open **Settings → Dashboards → Add dashboard**.
2. Name it **Shift +**, use URL `shift-plus`, select a calendar icon, and enable
   **Show in sidebar**.
3. Open the new dashboard, select **Edit dashboard → three-dot menu → Raw
   configuration editor**.
4. Replace the generated configuration with the example and save.
5. Adjust entity IDs if your installation generated different IDs.

## Shift + roster card

The integration ships a dependency-free custom card at:

`/shift_plus/shift-plus-roster-card.js`

After installing and restarting the integration:

1. Open **Settings → Dashboards → Resources**.
2. Add `/shift_plus/shift-plus-roster-card.js` as a **JavaScript module**.
3. Create a sidebar dashboard as above.
4. Use
   [`lovelace/shift-plus-custom-card-dashboard.yaml`](../lovelace/shift-plus-custom-card-dashboard.yaml)
   as its raw configuration.
5. Hard-refresh the browser if the card is not immediately listed.

The card is responsive, uses Home Assistant theme variables, highlights today,
and presents annual leave and overtime on a monthly grid. It safely handles
missing or unavailable entities. Its code can render duty categories, but
version 5.0.1 deliberately provides no daily-duty data to the card.

## Screenshot preview

A genuine sanitized dashboard screenshot will be added after capture from a
real installation. Follow the [screenshot checklist](images/README.md) so the
image contains no personal roster data, internal URLs, entity identifiers or
pairing credentials.

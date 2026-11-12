"use strict";

const assert = require("node:assert/strict");
const {
  SHIFT_COLORS,
  PRESENTATION,
  ShiftPlusRosterCard,
  calendarCells,
  coversMonth,
  escapeHtml,
  isoDate,
  monthKey,
  presentationValue,
} = require("../custom_components/shift_plus/frontend/shift-plus-roster-card.js");

assert.deepEqual(Object.keys(SHIFT_COLORS), ["E", "L", "N", "R"]);
assert.equal(PRESENTATION.font_size.large, "1.12");
assert.equal(presentationValue("font_size", "invalid", "medium"), "1");
assert.equal(calendarCells(2026, 8).length, 42);
assert.equal(isoDate(new Date(2026, 8, 2)), "2026-09-02");
assert.equal(monthKey(new Date(2027, 1, 1)), "2027-02");
assert.ok(coversMonth(
  { range_start: "2027-02-01", range_end: "2027-03-14" },
  new Date(2027, 1, 1),
));
assert.ok(!coversMonth(
  { range_start: "2026-11-30", range_end: "2027-02-21" },
  new Date(2027, 1, 1),
));
assert.equal(escapeHtml('<script token="secret">'), "&lt;script token=&quot;secret&quot;&gt;");

const renderCard = (states) => {
  const card = new ShiftPlusRosterCard();
  card.querySelectorAll = () => [];
  card.querySelector = () => null;
  card.setConfig({});
  card.hass = { states };
  return card.innerHTML;
};

const unavailable = renderCard({});
assert.match(unavailable, /calendar data is unavailable/);
assert.match(unavailable, /var\(--primary-text-color\)/);

const currentDate = isoDate(new Date());
const rendered = renderCard({
  "sensor.shift_calendar": {
    entity_id: "sensor.shift_calendar",
    state: "2",
    attributes: {
      card_data_version: 1,
      events: [
        { date: currentDate, kind: "annual_leave" },
        { date: currentDate, kind: "overtime" },
        null,
        { malformed: true },
      ],
      days: [],
    },
  },
});
assert.match(rendered, /Annual leave/);
assert.match(rendered, /Overtime/);
assert.match(rendered, /Duty data not yet synced/);

const rosterName = "Core and Non-Core Demonstration Roster With A Long Name";
const configured = new ShiftPlusRosterCard();
configured.querySelectorAll = () => [];
configured.querySelector = () => null;
configured.setConfig({
  font_size: "large",
  calendar_cell_size: "spacious",
  layout_density: "compact",
});
configured.hass = {
  states: {
    "sensor.shift_calendar": {
      entity_id: "sensor.shift_calendar",
      state: "2",
      attributes: { card_data_version: 1, events: [], days: [] },
    },
    "sensor.shift_active_roster": {
      entity_id: "sensor.shift_active_roster",
      state: rosterName,
      attributes: {},
    },
  },
};
assert.match(configured.innerHTML, /--sp-font-scale:1.12/);
assert.match(configured.innerHTML, /--sp-cell-height:70px/);
assert.match(configured.innerHTML, /--sp-grid-gap:4px/);
assert.match(configured.innerHTML, new RegExp(rosterName));
console.log("Shift + frontend tests passed");

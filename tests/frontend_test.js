"use strict";

const assert = require("node:assert/strict");
const {
  SHIFT_COLORS,
  ANDROID_CALENDAR,
  ROSTER_CARD_VERSION,
  PRESENTATION,
  ShiftPlusRosterCard,
  calendarCells,
  coversMonth,
  escapeHtml,
  isoDate,
  formatOvertime,
  monthKey,
  presentationValue,
} = require("../custom_components/shift_plus/frontend/shift-plus-roster-card.js");

assert.deepEqual(Object.keys(SHIFT_COLORS), ["E", "L", "N", "R"]);
assert.equal(SHIFT_COLORS.E, "#E0F0E1");
assert.equal(SHIFT_COLORS.L, "#DCEAF7");
assert.equal(SHIFT_COLORS.N, "#6685AD");
assert.equal(SHIFT_COLORS.R, "#F6DEE1");
assert.deepEqual(ANDROID_CALENDAR, {
  annualLeave: "#43A047", today: "#C81E1E", overtime: "#20242A",
});
assert.equal(formatOvertime({ state: "540", attributes: { unit_of_measurement: "min" } }), "9 h");
assert.equal(formatOvertime({ state: "9", attributes: { unit_of_measurement: "h" } }), "9 h");
assert.equal(formatOvertime({ state: "540", attributes: {} }), "540");
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
        { date: currentDate, kind: "annual_leave", portion: "morning" },
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
assert.match(rendered, /mdi:briefcase-outline/);
assert.match(rendered, /overtime-overlay/);
assert.match(rendered, /leave-half morning/);
assert.match(rendered, /--sp-android-today:#C81E1E/);
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

;(async () => {
const remoteCard = new ShiftPlusRosterCard();
remoteCard.setConfig({});
remoteCard.month = new Date(2027, 1, 1);
remoteCard.render = () => {};
remoteCard._hass = {
  states: {
    "sensor.shift_calendar": {
      entity_id: "sensor.shift_calendar",
      state: "0",
      attributes: {
        card_data_version: 1, range_start: "2026-11-09", range_end: "2027-01-31", days: [], events: [],
      },
    },
  },
  callApi: async (method, path) => {
    assert.equal(method, "GET");
    assert.match(path, /month=2027-02/);
    return {
      card_data_version: 1, card_version: ROSTER_CARD_VERSION, month: "2027-02",
      range_start: "2027-02-01", range_end: "2027-03-14", days: [{ date: "2027-02-01", duty: "E" }], events: [],
    };
  },
};
await remoteCard._ensureMonthData(remoteCard._calendarData());
assert.equal(remoteCard._remoteCalendar.month, "2027-02");
assert.equal(remoteCard._calendarData().days[0].duty, "E");

const mismatchedCard = new ShiftPlusRosterCard();
mismatchedCard.setConfig({});
mismatchedCard.month = new Date(2027, 1, 1);
mismatchedCard.render = () => {};
mismatchedCard._hass = {
  states: remoteCard._hass.states,
  callApi: async () => ({ card_data_version: 1, card_version: "old", month: "2027-02", days: [], events: [] }),
};
await mismatchedCard._ensureMonthData(mismatchedCard._calendarData());
assert.match(mismatchedCard._monthLoadErrors.get("2027-02"), /versions do not match/);
assert.ok(mismatchedCard._unavailableMonths.has("2027-02"));
console.log("Shift + frontend tests passed");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

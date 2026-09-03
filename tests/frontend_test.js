"use strict";

const assert = require("node:assert/strict");
const {
  SHIFT_COLORS,
  ShiftPlusRosterCard,
  calendarCells,
  escapeHtml,
  isoDate,
} = require("../custom_components/shift_plus/frontend/shift-plus-roster-card.js");

assert.deepEqual(Object.keys(SHIFT_COLORS), ["E", "L", "N", "R"]);
assert.equal(calendarCells(2026, 8).length, 42);
assert.equal(isoDate(new Date(2026, 8, 2)), "2026-09-02");
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
console.log("Shift + frontend tests passed");

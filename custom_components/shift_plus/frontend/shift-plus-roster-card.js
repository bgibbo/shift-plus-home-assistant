/* Shift + roster card. Dependency-free and intentionally contains no credentials. */

const SHIFT_COLORS = Object.freeze({
  E: "#72b879",
  L: "#8fc8ef",
  N: "#2457a6",
  R: "#e57373",
});

const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

const isoDate = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const calendarCells = (year, month) => {
  const first = new Date(year, month, 1);
  const mondayOffset = (first.getDay() + 6) % 7;
  const start = new Date(year, month, 1 - mondayOffset);
  return Array.from({ length: 42 }, (_, index) => {
    const value = new Date(start);
    value.setDate(start.getDate() + index);
    return value;
  });
};

const HTMLElementBase = typeof HTMLElement === "undefined" ? class {} : HTMLElement;

class ShiftPlusRosterCard extends HTMLElementBase {
  setConfig(config) {
    this.config = {
      title: "Shift +",
      calendar_entity: "sensor.shift_calendar",
      roster_entity: "sensor.shift_active_roster",
      status_entity: "sensor.shift_paired_devices",
      leave_entity: "sensor.shift_annual_leave",
      overtime_entity: "sensor.shift_overtime",
      ...config,
    };
    const now = new Date();
    this.month = new Date(now.getFullYear(), now.getMonth(), 1);
    this.selected = isoDate(now);
  }

  set hass(value) {
    this._hass = value;
    this.render();
  }

  getCardSize() { return 8; }

  _entity(configKey, suffix) {
    const configured = this._hass?.states?.[this.config[configKey]];
    if (configured) return configured;
    return Object.values(this._hass?.states ?? {}).find((entity) =>
      entity.entity_id.startsWith("sensor.") &&
      entity.attributes?.friendly_name?.toLowerCase().endsWith(suffix));
  }

  _calendarData() {
    const entity = this._entity("calendar_entity", "calendar");
    if (!entity || ["unknown", "unavailable"].includes(entity.state)) {
      return { available: false, events: [], days: [] };
    }
    return {
      available: true,
      events: Array.isArray(entity.attributes.events) ? entity.attributes.events : [],
      days: Array.isArray(entity.attributes.days) ? entity.attributes.days : [],
    };
  }

  _dayMap(items) {
    const map = new Map();
    for (const item of items) {
      if (!item || typeof item.date !== "string") continue;
      const list = map.get(item.date) ?? [];
      list.push(item);
      map.set(item.date, list);
    }
    return map;
  }

  render() {
    if (!this._hass || !this.config) return;
    const calendar = this._calendarData();
    const events = this._dayMap(calendar.events);
    const duties = this._dayMap(calendar.days);
    const today = isoDate(new Date());
    const roster = this._entity("roster_entity", "active roster");
    const status = this._entity("status_entity", "paired devices");
    const leave = this._entity("leave_entity", "annual leave");
    const overtime = this._entity("overtime_entity", "overtime");
    const monthLabel = this.month.toLocaleDateString(undefined, {
      month: "long", year: "numeric",
    });
    const selectedEvents = events.get(this.selected) ?? [];
    const selectedDuty = (duties.get(this.selected) ?? [])[0]?.duty;
    const cells = calendarCells(this.month.getFullYear(), this.month.getMonth())
      .map((date) => {
        const key = isoDate(date);
        const duty = (duties.get(key) ?? [])[0]?.duty;
        const dutyCode = ["E", "L", "N", "R"].includes(duty) ? duty : "";
        const markers = events.get(key) ?? [];
        const classes = [
          "day",
          date.getMonth() === this.month.getMonth() ? "" : "outside",
          key === today ? "today" : "",
          key === this.selected ? "selected" : "",
          dutyCode ? `duty-${dutyCode}` : "",
        ].filter(Boolean).join(" ");
        const dots = [
          markers.some((item) => item.kind === "annual_leave")
            ? '<span class="marker leave" title="Annual leave"></span>' : "",
          markers.some((item) => item.kind === "overtime")
            ? '<span class="marker overtime" title="Overtime"></span>' : "",
        ].join("");
        return `<button class="${classes}" data-date="${key}" aria-label="${key}">
          <span>${date.getDate()}</span><strong>${escapeHtml(dutyCode)}</strong>
          <span class="markers">${dots}</span></button>`;
      }).join("");
    const detail = [
      selectedDuty ? `Duty ${escapeHtml(selectedDuty)}` : "Duty data not yet synced",
      selectedEvents.some((item) => item.kind === "annual_leave") ? "Annual leave" : "",
      selectedEvents.some((item) => item.kind === "overtime") ? "Overtime" : "",
    ].filter(Boolean).join(" · ");
    this.innerHTML = `<ha-card>
      <style>
        :host{--sp-blue:#45699b;display:block}.wrap{padding:18px;color:var(--primary-text-color)}
        header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}
        h2{margin:0;font-size:1.45rem}.subtitle{color:var(--secondary-text-color);font-size:.9rem}
        .summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-bottom:14px}
        .metric{background:var(--secondary-background-color);border-radius:12px;padding:10px;min-width:0}
        .metric b,.metric span{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .metric span{font-size:.75rem;color:var(--secondary-text-color);margin-bottom:3px}
        .month{display:flex;align-items:center;justify-content:space-between;margin:8px 0}
        .month button{border:0;background:transparent;color:var(--primary-text-color);font-size:1.5rem;cursor:pointer}
        .week,.grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:5px}
        .week span{text-align:center;font-size:.72rem;font-weight:700;color:var(--secondary-text-color)}
        .day{position:relative;min-height:58px;border:0;border-radius:10px;background:var(--secondary-background-color);color:var(--primary-text-color);padding:6px;cursor:pointer}
        .day strong{display:block;margin-top:4px}.outside{opacity:.38}.today{outline:3px solid var(--sp-blue)}
        .selected{box-shadow:inset 0 0 0 2px var(--primary-text-color)}
        .duty-E{background:${SHIFT_COLORS.E}}.duty-L{background:${SHIFT_COLORS.L}}
        .duty-N{background:${SHIFT_COLORS.N};color:#fff}.duty-R{background:${SHIFT_COLORS.R}}
        .markers{position:absolute;display:flex;gap:3px;bottom:5px;left:50%;transform:translateX(-50%)}
        .marker{width:7px;height:7px;border-radius:50%}.leave{background:#f5c542}.overtime{background:#7e57c2}
        .detail{margin-top:14px;padding:12px;border-left:4px solid var(--sp-blue);background:var(--secondary-background-color);border-radius:8px}
        .empty{padding:18px;text-align:center;color:var(--secondary-text-color)}
        @media(max-width:520px){.wrap{padding:12px}.day{min-height:48px;padding:4px}.summary{grid-template-columns:1fr}.week,.grid{gap:3px}}
      </style>
      <div class="wrap"><header><div><h2>${escapeHtml(this.config.title)}</h2>
      <div class="subtitle">${escapeHtml(new Date().toLocaleDateString(undefined, { weekday:"long", day:"numeric", month:"long" }))}</div></div>
      <ha-icon icon="mdi:calendar-account"></ha-icon></header>
      <div class="summary">
        <div class="metric"><span>Active roster</span><b>${escapeHtml(roster?.state ?? "Unavailable")}</b></div>
        <div class="metric"><span>Annual leave</span><b>${escapeHtml(leave ? `${leave.state} days` : "Unavailable")}</b></div>
        <div class="metric"><span>Overtime</span><b>${escapeHtml(overtime ? `${overtime.state} h` : "Unavailable")}</b></div>
      </div>
      ${calendar.available ? `<div class="month"><button data-nav="prev" aria-label="Previous month">‹</button><b>${escapeHtml(monthLabel)}</b><button data-nav="next" aria-label="Next month">›</button></div>
      <div class="week"><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span></div><div class="grid">${cells}</div>
      <div class="detail"><b>${escapeHtml(this.selected)}</b><div>${detail}</div></div>`
      : '<div class="empty">Shift + calendar data is unavailable. Pair and sync the Android app, then try again.</div>'}
      <div class="subtitle" style="margin-top:12px">Sync: ${escapeHtml(status?.attributes?.sync_status ?? "unavailable")}</div>
      </div></ha-card>`;
    this.querySelectorAll("[data-date]").forEach((button) => button.addEventListener("click", () => {
      this.selected = button.dataset.date;
      this.render();
    }));
    this.querySelector('[data-nav="prev"]')?.addEventListener("click", () => {
      this.month = new Date(this.month.getFullYear(), this.month.getMonth() - 1, 1);
      this.render();
    });
    this.querySelector('[data-nav="next"]')?.addEventListener("click", () => {
      this.month = new Date(this.month.getFullYear(), this.month.getMonth() + 1, 1);
      this.render();
    });
  }
}

if (typeof customElements !== "undefined" && !customElements.get("shift-plus-roster-card")) {
  customElements.define("shift-plus-roster-card", ShiftPlusRosterCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "shift-plus-roster-card",
    name: "Shift + roster",
    description: "Monthly Shift + roster, leave, overtime, and sync status.",
  });
}

if (typeof module !== "undefined") {
  module.exports = {
    SHIFT_COLORS,
    ShiftPlusRosterCard,
    calendarCells,
    escapeHtml,
    isoDate,
  };
}

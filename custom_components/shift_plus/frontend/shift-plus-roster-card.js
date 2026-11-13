/* Shift + roster card. Dependency-free and intentionally contains no credentials. */

const SHIFT_COLORS = Object.freeze({
  // Shift + Android's standard CalendarAppearance palette.
  E: "#E0F0E1",
  L: "#DCEAF7",
  N: "#6685AD",
  R: "#F6DEE1",
});
const ANDROID_CALENDAR = Object.freeze({
  annualLeave: "#43A047",
  today: "#C81E1E",
  overtime: "#20242A",
});
const ROSTER_CARD_VERSION = "2026.11.13.2";

const PRESENTATION = Object.freeze({
  font_size: Object.freeze({ small: ".9", medium: "1", large: "1.12" }),
  calendar_cell_size: Object.freeze({ compact: "46px", comfortable: "58px", spacious: "70px" }),
  layout_density: Object.freeze({ compact: "4px", comfortable: "6px", spacious: "9px" }),
});

const presentationValue = (group, value, fallback) =>
  PRESENTATION[group][value] ?? PRESENTATION[group][fallback];

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

const monthKey = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;

const coversMonth = (calendar, month) => {
  const cells = calendarCells(month.getFullYear(), month.getMonth());
  const first = isoDate(cells[0]);
  const last = isoDate(cells.at(-1));
  return calendar.range_start <= first && calendar.range_end >= last;
};

const formatOvertime = (entity) => {
  if (!entity) return "Unavailable";
  const value = Number(entity.state);
  if (!Number.isFinite(value)) return String(entity.state ?? "Unavailable");
  const unit = String(entity.attributes?.unit_of_measurement ?? "").toLowerCase();
  if (["min", "minute", "minutes"].includes(unit)) {
    const hours = value / 60;
    return `${Number.isInteger(hours) ? hours : hours.toFixed(2)} h`;
  }
  if (["h", "hr", "hour", "hours"].includes(unit)) return `${value} h`;
  return unit ? `${value} ${unit}` : String(value);
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
      // Defaults adapt at mobile and tablet breakpoints in the card stylesheet.
      font_size: "medium",
      calendar_cell_size: "comfortable",
      layout_density: "comfortable",
      ...config,
    };
    const now = new Date();
    this.month = new Date(now.getFullYear(), now.getMonth(), 1);
    this.selected = isoDate(now);
    this._remoteCalendar = null;
    this._loadingMonth = null;
    this._unavailableMonths = new Set();
    this._monthLoadErrors = new Map();
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
    if (
      !entity ||
      ["unknown", "unavailable"].includes(entity.state) ||
      entity.attributes?.card_data_version !== 1 ||
      !Array.isArray(entity.attributes.days)
    ) {
      return { available: false, events: [], days: [], range_start: "", range_end: "" };
    }
    const remote = this._remoteCalendar;
    if (remote?.month === monthKey(this.month)) return remote;
    return {
      available: true,
      events: Array.isArray(entity.attributes.events) ? entity.attributes.events : [],
      days: Array.isArray(entity.attributes.days) ? entity.attributes.days : [],
      range_start: entity.attributes.range_start ?? "",
      range_end: entity.attributes.range_end ?? "",
    };
  }

  async _ensureMonthData(calendar) {
    if (!calendar.available || coversMonth(calendar, this.month) || !this._hass?.callApi) return;
    const month = monthKey(this.month);
    if (
      this._loadingMonth === month || this._remoteCalendar?.month === month ||
      this._unavailableMonths.has(month)
    ) return;
    this._loadingMonth = month;
    try {
      // hass.callApi supplies the /api/ prefix and user authentication.
      // Supplying an absolute /api/ path produces /api//api/... and the
      // authenticated month request is rejected by Home Assistant.
      const data = await this._hass.callApi(
        "GET", `shift_plus/roster-card?month=${encodeURIComponent(month)}`,
      );
      if (
        data?.card_data_version === 1 && data.card_version === ROSTER_CARD_VERSION &&
        data.month === month &&
        Array.isArray(data.days) && Array.isArray(data.events)
      ) {
        this._remoteCalendar = { ...data, available: true };
        this._monthLoadErrors.delete(month);
      } else {
        this._monthLoadErrors.set(month, "The Home Assistant card and backend versions do not match.");
        this._unavailableMonths.add(month);
      }
    } catch (error) {
      this._monthLoadErrors.set(
        month,
        `Could not load this month from Home Assistant${error?.message ? `: ${error.message}` : "."}`,
      );
      this._unavailableMonths.add(month);
    } finally {
      if (this._loadingMonth === month) this._loadingMonth = null;
      this.render();
    }
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
    const fontScale = presentationValue("font_size", this.config.font_size, "medium");
    const cellHeight = presentationValue(
      "calendar_cell_size", this.config.calendar_cell_size, "comfortable",
    );
    const gridGap = presentationValue(
      "layout_density", this.config.layout_density, "comfortable",
    );
    const activeMonth = monthKey(this.month);
    const monthLoadError = this._monthLoadErrors.get(activeMonth);
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
        const leave = markers.find((item) => item.kind === "annual_leave");
        const hasOvertime = markers.some((item) => item.kind === "overtime");
        const leaveShade = leave?.portion === "morning"
          ? '<span class="leave-half morning"></span>'
          : leave?.portion === "afternoon"
          ? '<span class="leave-half afternoon"></span>' : "";
        const overtimeShade = hasOvertime ? '<span class="overtime-overlay"></span>' : "";
        const leaveIcon = leave
          ? '<ha-icon class="annual-leave" icon="mdi:briefcase-outline" title="Annual leave"></ha-icon>'
          : "";
        const label = [key, dutyCode ? `duty ${dutyCode}` : "", leave ? "annual leave" : "", hasOvertime ? "overtime" : ""]
          .filter(Boolean).join(", ");
        return `<button class="${classes}" data-date="${key}" aria-label="${escapeHtml(label)}">
          ${overtimeShade}${leaveShade}<span class="day-number">${date.getDate()}</span>
          <strong>${escapeHtml(dutyCode)}</strong>${leaveIcon}</button>`;
      }).join("");
    const detail = [
      selectedDuty ? `Duty ${escapeHtml(selectedDuty)}` : "Duty data not yet synced",
      selectedEvents.some((item) => item.kind === "annual_leave") ? "Annual leave" : "",
      selectedEvents.some((item) => item.kind === "overtime") ? "Overtime" : "",
    ].filter(Boolean).join(" · ");
    this.innerHTML = `<ha-card data-shift-plus-card-version="${ROSTER_CARD_VERSION}">
      <style>
        :host{--sp-blue:#45699b;--sp-android-today:${ANDROID_CALENDAR.today};--sp-annual-leave:${ANDROID_CALENDAR.annualLeave};--sp-overtime:${ANDROID_CALENDAR.overtime};--sp-font-scale:${fontScale};--sp-cell-height:${cellHeight};--sp-grid-gap:${gridGap};display:block}.wrap{padding:18px;color:var(--primary-text-color);font-size:calc(1rem * var(--sp-font-scale))}
        header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}
        h2{margin:0;font-size:1.45rem}.subtitle{color:var(--secondary-text-color);font-size:.9rem}
        .summary{display:grid;grid-template-columns:minmax(11rem,2fr) repeat(2,minmax(0,1fr));gap:8px;margin-bottom:14px}
        .metric{background:var(--secondary-background-color);border-radius:12px;padding:10px;min-width:0}
        .metric b,.metric span{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .metric.roster b{white-space:normal;overflow:visible;text-overflow:clip;overflow-wrap:anywhere;line-height:1.25}
        .metric span{font-size:.75rem;color:var(--secondary-text-color);margin-bottom:3px}
        .month{display:flex;align-items:center;justify-content:space-between;margin:8px 0}
        .month button{border:0;background:transparent;color:var(--primary-text-color);font-size:1.5rem;cursor:pointer}
        .week,.grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:var(--sp-grid-gap)}
        .week span{text-align:center;font-size:.72rem;font-weight:700;color:var(--secondary-text-color)}
        .day{position:relative;isolation:isolate;display:flex;flex-direction:column;align-items:center;min-height:var(--sp-cell-height);border:0;border-radius:10px;background:var(--secondary-background-color);color:var(--primary-text-color);padding:6px;cursor:pointer;overflow:hidden}
        .day-number{align-self:flex-start;font-weight:700;line-height:1}.day strong{display:block;margin-top:6px;font-size:1.1em}.outside{opacity:.68;box-shadow:inset 0 0 0 2px var(--primary-text-color)}.today{box-shadow:inset 0 0 0 4px var(--sp-android-today)}
        .selected:not(.today){box-shadow:inset 0 0 0 2px var(--primary-text-color)}
        .duty-E{background:${SHIFT_COLORS.E}}.duty-L{background:${SHIFT_COLORS.L}}
        .duty-N{background:${SHIFT_COLORS.N};color:#fff}.duty-R{background:${SHIFT_COLORS.R}}
        .overtime-overlay{position:absolute;z-index:-1;inset:0 0 0 50%;background:rgba(32,36,42,.38);border-radius:0 8px 8px 0}.leave-half{position:absolute;z-index:-1;top:0;bottom:0;width:50%;background:rgba(67,160,71,.16)}.leave-half.morning{left:0;border-radius:8px 0 0 8px}.leave-half.afternoon{right:0;border-radius:0 8px 8px 0}.annual-leave{position:absolute;top:3px;right:3px;color:var(--sp-annual-leave);--mdc-icon-size:14px}
        .detail{margin-top:14px;padding:12px;border-left:4px solid var(--sp-blue);background:var(--secondary-background-color);border-radius:8px}
        .month-error{margin-top:12px;padding:10px;border-left:4px solid var(--error-color,#c81e1e);background:var(--secondary-background-color);border-radius:8px;color:var(--primary-text-color)}
        .empty{padding:18px;text-align:center;color:var(--secondary-text-color)}
        @media(max-width:520px){:host{--sp-cell-height:min(var(--sp-cell-height),48px);--sp-grid-gap:min(var(--sp-grid-gap),3px)}.wrap{padding:12px}.day{padding:4px}.summary{grid-template-columns:1fr}}
        @media(min-width:521px) and (max-width:800px){:host{--sp-cell-height:min(var(--sp-cell-height),52px)}.summary{grid-template-columns:repeat(2,minmax(0,1fr))}.metric.roster{grid-column:1 / -1}}
      </style>
      <div class="wrap"><header><div><h2>${escapeHtml(this.config.title)}</h2>
      <div class="subtitle">${escapeHtml(new Date().toLocaleDateString(undefined, { weekday:"long", day:"numeric", month:"long" }))}</div></div>
      <ha-icon icon="mdi:calendar-account"></ha-icon></header>
      <div class="summary">
        <div class="metric roster"><span>Active roster</span><b title="${escapeHtml(roster?.state ?? "Unavailable")}">${escapeHtml(roster?.state ?? "Unavailable")}</b></div>
        <div class="metric"><span>Annual leave</span><b>${escapeHtml(leave ? `${leave.state} days` : "Unavailable")}</b></div>
        <div class="metric"><span>Overtime</span><b>${escapeHtml(formatOvertime(overtime))}</b></div>
      </div>
      ${calendar.available ? `<div class="month"><button data-nav="prev" aria-label="Previous month">‹</button><b>${escapeHtml(monthLabel)}</b><button data-nav="next" aria-label="Next month">›</button></div>
      <div class="week"><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span></div><div class="grid">${cells}</div>
      <div class="detail"><b>${escapeHtml(this.selected)}</b><div>${detail}</div></div>`
      : '<div class="empty">Shift + calendar data is unavailable. Pair and sync the Android app, then try again.</div>'}
      ${monthLoadError ? `<div class="month-error" role="alert">${escapeHtml(monthLoadError)}</div>` : ""}
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
    void this._ensureMonthData(calendar);
  }
}

console.info(`[Shift +] roster card ${ROSTER_CARD_VERSION} loaded`);

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
  };
}

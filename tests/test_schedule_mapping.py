from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from custom_components.shift_plus.coordinator import (
    ShiftPlusCoordinator,
    _synced_time_label,
)
from custom_components.shift_plus.roster.calculations import work_boundaries
from custom_components.shift_plus.roster.engine import Duty


def duty(category: str, time_label: str, *, roster_id: str = "core") -> Duty:
    return Duty(
        date=date(2026, 9, 1),
        roster_id=roster_id,
        unit_id="unit-a",
        cycle_day=1,
        cycle_length=8,
        code=category[:1].upper(),
        category=category,
        time_label=time_label,
        recovery_label=None,
        mandatory_rest=False,
        operational_verification=True,
        break_minutes=None,
    )


@pytest.mark.parametrize(
    ("category", "start_key", "finish_key", "expected"),
    [
        ("early", "earlyStartMinutes", "earlyFinishMinutes", "06:30-14:30"),
        ("late", "lateStartMinutes", "lateFinishMinutes", "16:00-02:00"),
        ("night", "nightStartMinutes", "nightFinishMinutes", "22:00-06:00"),
    ],
)
def test_synced_category_schedule_overrides_builtin(
    category: str, start_key: str, finish_key: str, expected: str
) -> None:
    start, finish = {
        "early": (390, 870),
        "late": (960, 120),
        "night": (1320, 360),
    }[category]
    assert (
        _synced_time_label(
            duty(category, "07:00-15:00"), {start_key: start, finish_key: finish}
        )
        == expected
    )


def test_day_roster_variants_use_synced_schedule() -> None:
    assert (
        _synced_time_label(
            duty("tour", "08:00-16:00", roster_id="eight-hour"),
            {"eightHourStartMinutes": 9 * 60},
        )
        == "09:00-17:00"
    )
    assert (
        _synced_time_label(
            duty("tour", "09:00-17:00", roster_id="garda-staff"),
            {"gardaStaffStartMinutes": 8 * 60, "gardaStaffFinishMinutes": 16 * 60 + 30},
        )
        == "08:00-16:30"
    )


def test_non_core_start_offset_matches_android() -> None:
    assert (
        _synced_time_label(
            duty("late", "14:00-24:00", roster_id="non-core-2"),
            {"nonCoreStartMinutes": 8 * 60},
        )
        == "15:00-01:00"
    )


@pytest.mark.parametrize(
    "legacy", [None, "", " ", "late", "16:00–02:00", "25:00-02:00"]
)
def test_missing_or_malformed_legacy_value_cannot_suppress_builtin(
    legacy: str | None,
) -> None:
    coordinator = object.__new__(ShiftPlusCoordinator)
    coordinator.entry = SimpleNamespace(
        data={"roster_id": "core", "unit_id": "unit-a", "late_time": legacy},
        options={},
    )
    coordinator.store = SimpleNamespace(records=lambda record_type: [])
    original = duty("late", "14:00-24:00")
    assert coordinator._configured(original).time_label == "14:00-24:00"


def test_valid_legacy_value_is_retained_for_standalone_installations() -> None:
    coordinator = object.__new__(ShiftPlusCoordinator)
    coordinator.entry = SimpleNamespace(
        data={"roster_id": "core", "unit_id": "unit-a", "late_time": "15:00-01:00"},
        options={},
    )
    coordinator.store = SimpleNamespace(records=lambda record_type: [])
    assert (
        coordinator._configured(duty("late", "14:00-24:00")).time_label == "15:00-01:00"
    )


def test_synced_schedule_survives_store_reload_and_precedes_legacy() -> None:
    payload = {
        "active_roster_id": "core",
        "active_unit_id": "unit-a",
        "roster_schedule_settings": {
            "lateStartMinutes": 16 * 60,
            "lateFinishMinutes": 2 * 60,
        },
    }
    coordinator = object.__new__(ShiftPlusCoordinator)
    coordinator.entry = SimpleNamespace(
        data={"roster_id": "core", "unit_id": "unit-a", "late_time": "15:00-01:00"},
        options={},
    )
    coordinator.store = SimpleNamespace(
        records=lambda record_type: (
            [payload] if record_type == "active_configuration" else []
        )
    )
    assert (
        coordinator._configured(duty("late", "14:00-24:00")).time_label == "16:00-02:00"
    )


def test_overnight_and_24_hour_finish_ranges_are_preserved() -> None:
    for label in ("16:00-02:00", "15:00-01:00", "14:00-24:00"):
        roster_range = duty("late", label).roster_range()
        assert roster_range is not None
        assert roster_range[1].date() == date(2026, 9, 2)


def test_rostered_times_remain_on_full_day_leave_but_effective_times_do_not() -> None:
    shift = duty("late", "14:00-24:00")
    full = work_boundaries(shift, leave_portion="fullDay")
    assert full.roster_start is not None
    assert full.roster_end is not None
    assert full.effective_start is None
    assert full.effective_end is None
    assert full.booking_on_opens is None
    assert full.booking_off_opens is None


def test_half_day_leave_suppresses_only_relevant_booking_window() -> None:
    shift = duty("late", "14:00-24:00")
    morning = work_boundaries(shift, leave_portion="morning")
    afternoon = work_boundaries(shift, leave_portion="afternoon")
    assert morning.booking_on_opens is None
    assert morning.booking_off_opens is not None
    assert afternoon.booking_on_opens is not None
    assert afternoon.booking_off_opens is None

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from custom_components.shift_plus.coordinator import ShiftPlusCoordinator
from custom_components.shift_plus.roster.engine import RosterEngine


class EmptyStore:
    def records(self, record_type: str) -> list[dict]:
        return []


@pytest.mark.asyncio
async def test_coordinator_setup_uses_ha_timezone_without_naive_comparison(
    monkeypatch,
) -> None:
    zone = ZoneInfo("Europe/Dublin")
    fixed_now = datetime(2026, 8, 10, 12, 0, tzinfo=zone)
    monkeypatch.setattr(
        "custom_components.shift_plus.coordinator.dt_util.now",
        lambda requested_zone=None: fixed_now,
    )

    coordinator = object.__new__(ShiftPlusCoordinator)
    coordinator.entry = SimpleNamespace(
        data={
            "roster_id": "core",
            "unit_id": "unit-a",
            "include_tour_briefing": True,
            "book_on_offset_minutes": 8,
            "book_off_offset_minutes": 8,
        },
        options={},
    )
    coordinator.store = EmptyStore()
    coordinator.engine = RosterEngine()
    coordinator.time_zone = zone

    data = await coordinator._async_update_data()

    assert data["now"] == fixed_now
    assert data["now"].tzinfo is zone
    for key in ("next_book_on", "next_book_off"):
        assert data[key] is None or data[key].tzinfo is zone
    for value in (
        data["boundaries"].roster_start,
        data["boundaries"].roster_end,
        data["boundaries"].effective_start,
        data["boundaries"].effective_end,
    ):
        assert value is None or value.tzinfo is zone


@pytest.mark.asyncio
async def test_stored_roster_progresses_across_midnight_without_phone_sync(
    monkeypatch,
) -> None:
    zone = ZoneInfo("Europe/Dublin")
    clock = [datetime(2026, 8, 10, 23, 59, tzinfo=zone)]
    monkeypatch.setattr(
        "custom_components.shift_plus.coordinator.dt_util.now",
        lambda requested_zone=None: clock[0],
    )

    coordinator = object.__new__(ShiftPlusCoordinator)
    coordinator.entry = SimpleNamespace(
        data={
            "roster_id": "core",
            "unit_id": "unit-a",
            "include_tour_briefing": False,
            "book_on_offset_minutes": 8,
            "book_off_offset_minutes": 8,
        },
        options={},
    )
    coordinator.store = EmptyStore()
    coordinator.engine = RosterEngine()
    coordinator.time_zone = zone

    snapshots = []
    for day in range(4):
        clock[0] = datetime(2026, 8, 10 + day, 0, 1, tzinfo=zone)
        snapshots.append(await coordinator._async_update_data())

    assert [item["now"].date().isoformat() for item in snapshots] == [
        "2026-08-10",
        "2026-08-11",
        "2026-08-12",
        "2026-08-13",
    ]
    assert [item["duty"].date for item in snapshots] == [
        item["now"].date() for item in snapshots
    ]
    assert all(
        item["tomorrow"].date.toordinal() == item["duty"].date.toordinal() + 1
        for item in snapshots
    )
    assert len({item["duty"].cycle_day for item in snapshots}) == 4


def test_dublin_dst_offsets_follow_local_wall_clock() -> None:
    zone = ZoneInfo("Europe/Dublin")
    winter = datetime(2026, 1, 15, 8, 0, tzinfo=zone)
    summer = datetime(2026, 7, 15, 8, 0, tzinfo=zone)

    assert winter.utcoffset().total_seconds() == 0
    assert summer.utcoffset().total_seconds() == 3600

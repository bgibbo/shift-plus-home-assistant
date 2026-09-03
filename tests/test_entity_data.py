"""Tests for sanitized dashboard entity projections."""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

MODULE_PATH = (
    Path(__file__).parents[1] / "custom_components" / "shift_plus" / "entity_data.py"
)
SPEC = importlib.util.spec_from_file_location("shift_plus_entity_data", MODULE_PATH)
assert SPEC and SPEC.loader
entity_data = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(entity_data)


def record(record_type: str, payload: dict, *, tombstone: bool = False) -> dict:
    return {
        "record_type": record_type,
        "record_id": "internal-id",
        "payload": payload,
        "tombstone": tombstone,
        "operation_id": "must-not-leak",
    }


def sample_data() -> dict:
    return {
        "records": {
            "active_configuration:active": record(
                "active_configuration",
                {
                    "active_roster_id": "core-roster",
                    "active_unit_id": "unit-a",
                    "organisation_name": "Private employer",
                },
            ),
            "annual_leave:one": record(
                "annual_leave",
                {
                    "start_date": "2026-09-10",
                    "number_of_days": 2,
                    "day_portion": "full",
                },
            ),
            "overtime:one": record(
                "overtime",
                {
                    "date": "2026-09-12",
                    "start_minutes": 1320,
                    "finish_minutes": 120,
                    "description": "Private note",
                },
            ),
        }
    }


def test_dashboard_projection_uses_real_records() -> None:
    data = sample_data()
    assert entity_data.active_configuration(data) == {
        "roster_id": "core-roster",
        "unit_id": "unit-a",
    }
    assert entity_data.leave_summary(data, date(2026, 9, 9)) == {
        "days": 2,
        "today": False,
        "next_date": "2026-09-10",
    }
    assert entity_data.overtime_summary(data, date(2026, 9, 9)) == {
        "hours": 4.0,
        "entries": 1,
        "next_date": "2026-09-12",
    }


def test_dashboard_projection_omits_sensitive_and_free_text_fields() -> None:
    rendered = repr(entity_data.calendar_events(sample_data()))
    assert "Private note" not in rendered
    assert "Private employer" not in rendered
    assert "internal-id" not in rendered
    assert "must-not-leak" not in rendered


def test_malformed_and_deleted_records_are_ignored() -> None:
    data = {
        "records": {
            "bad": record("annual_leave", {"start_date": "not-a-date"}),
            "deleted": record(
                "overtime",
                {"date": "2026-09-12", "start_minutes": 10, "finish_minutes": 20},
                tombstone=True,
            ),
            "wrong": "not-a-record",
        }
    }
    assert entity_data.calendar_events(data) == []
    assert entity_data.active_configuration(data) == {}


def test_half_day_leave_counts_as_half_a_day() -> None:
    data = {
        "records": {
            "annual_leave:half": record(
                "annual_leave",
                {
                    "start_date": "2026-09-10",
                    "number_of_days": 1,
                    "day_portion": "firstHalf",
                },
            )
        }
    }
    assert entity_data.leave_summary(data, date(2026, 9, 1))["days"] == 0.5

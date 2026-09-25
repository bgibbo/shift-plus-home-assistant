from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from custom_components.shift_plus.roster.engine import RosterEngine

ROOT = Path(__file__).resolve().parents[1]
ROSTER_DIR = ROOT / "custom_components" / "shift_plus" / "roster"


def test_every_dart_golden_case_matches_python() -> None:
    engine = RosterEngine()
    payload = json.loads(
        (ROSTER_DIR / "roster_golden.v1.json").read_text(encoding="utf-8")
    )
    assert payload["version"] == engine.definition_version
    for case in payload["cases"]:
        duty = engine.duty(
            date.fromisoformat(case["date"]), case["roster_id"], case["unit_id"]
        )
        assert duty.cycle_day == case["cycle_day"], case
        assert duty.code == case["code"], case
        assert duty.category == case["category"], case
        assert duty.time_label == case["time"], case
        assert duty.recovery_label == case["recovery_label"], case
        assert duty.mandatory_rest == case["mandatory_rest"], case


def test_engine_handles_dates_before_anchor() -> None:
    engine = RosterEngine()
    first = engine.duty(date(1999, 12, 31), "core", "unit-a")
    repeated = engine.duty(date(1999, 12, 31).replace(year=2000), "core", "unit-a")
    assert 1 <= first.cycle_day <= first.cycle_length
    assert 1 <= repeated.cycle_day <= repeated.cycle_length


def test_all_rosters_have_units_and_work() -> None:
    engine = RosterEngine()
    for roster_id in engine.roster_ids:
        assert engine.unit_ids(roster_id)
        next_duty = engine.next_working_duty(
            date(2026, 8, 9), roster_id, engine.unit_ids(roster_id)[0]
        )
        assert next_duty.working

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

import custom_components.shift_plus.frontend as frontend
from custom_components.shift_plus.api import RosterCardView
from custom_components.shift_plus.const import DOMAIN
from custom_components.shift_plus.frontend import (
    FRONTEND_RESOURCE_URL,
    FRONTEND_STATIC_URL,
    async_ensure_lovelace_resource,
    async_remove_frontend_resource,
)
from custom_components.shift_plus.roster.engine import RosterEngine
from custom_components.shift_plus.sensor import (
    CompatibilitySummarySensor,
    _roster_card_data,
    roster_card_data_for_range,
)


def test_manifest_declares_lovelace_dependency() -> None:
    manifest = Path("custom_components/shift_plus/manifest.json").read_text()

    assert '"dependencies": ["http", "lovelace"]' in manifest


class _Resources:
    def __init__(self) -> None:
        self.loaded = False
        self.items: list[dict] = []
        self.created: list[dict] = []
        self.deleted: list[str] = []

    async def async_load(self) -> None:
        self.loaded = True

    def async_items(self) -> list[dict]:
        return self.items

    async def async_create_item(self, item: dict) -> dict:
        created = {"id": "shift-plus-card", **item}
        self.items.append(created)
        self.created.append(created)
        return created

    async def async_delete_item(self, item_id: str) -> None:
        self.deleted.append(item_id)
        self.items = [item for item in self.items if item.get("id") != item_id]


@pytest.mark.asyncio
async def test_frontend_script_is_served_from_the_integration(monkeypatch) -> None:
    registered = []
    callbacks = []

    class Http:
        async def async_register_static_paths(self, paths) -> None:
            registered.extend(paths)

    monkeypatch.setattr(
        frontend,
        "async_at_started",
        lambda hass, callback: callbacks.append((hass, callback)),
    )
    hass = SimpleNamespace(data={DOMAIN: {}}, http=Http())

    await frontend.async_setup_frontend(hass)

    assert len(registered) == 1
    assert registered[0].url_path == FRONTEND_STATIC_URL
    assert Path(registered[0].path).name == "shift-plus-roster-card.js"
    assert registered[0].cache_headers is False
    assert callbacks == [(hass, frontend.async_ensure_lovelace_resource)]


@pytest.mark.asyncio
async def test_frontend_resource_is_registered_once_and_removed() -> None:
    resources = _Resources()
    hass = SimpleNamespace(data={DOMAIN: {}, "lovelace": {"resources": resources}})

    await async_ensure_lovelace_resource(hass)
    await async_ensure_lovelace_resource(hass)

    assert resources.loaded
    assert resources.created == [
        {
            "id": "shift-plus-card",
            "url": FRONTEND_RESOURCE_URL,
            "res_type": "module",
        }
    ]
    await async_remove_frontend_resource(hass)
    assert resources.deleted == ["shift-plus-card"]

    resources.items.append({"id": "existing-card", "url": FRONTEND_RESOURCE_URL})
    hass.data[DOMAIN] = {}
    await async_remove_frontend_resource(hass)
    assert resources.deleted == ["shift-plus-card"]


@pytest.mark.asyncio
async def test_legacy_frontend_resource_is_not_changed_or_owned(caplog) -> None:
    resources = _Resources()
    resources.items.append({"id": "user-resource", "url": FRONTEND_STATIC_URL})
    hass = SimpleNamespace(data={DOMAIN: {}, "lovelace": {"resources": resources}})

    await async_ensure_lovelace_resource(hass)

    assert resources.created == []
    assert "older URL" in caplog.text
    assert "frontend_resource_id" not in hass.data[DOMAIN]


def test_roster_card_contract_is_bounded_and_has_marker_only_data() -> None:
    class Engine:
        def duty(self, day, roster_id, unit_id):
            return SimpleNamespace(code="E" if day.day % 2 else "R")

    class Store:
        def records(self, kind):
            if kind == "annual_leave":
                return [
                    {
                        "id": "private-leave-id",
                        "start_date": "2026-09-21",
                        "number_of_days": 2,
                        "day_portion": "morning",
                        "description": "Must not be exposed",
                    }
                ]
            return [
                {
                    "id": "private-overtime-id",
                    "date": "2026-09-23",
                    "description": "Must not be exposed",
                }
            ]

    coordinator = SimpleNamespace(
        data={
            "now": datetime(2026, 9, 21, tzinfo=UTC),
            "roster_id": "core",
            "unit_id": "unit-a",
        },
        engine=Engine(),
        _configured=lambda duty: duty,
    )
    data = _roster_card_data(SimpleNamespace(coordinator=coordinator, store=Store()))

    assert data["card_data_version"] == 1
    assert len(data["days"]) == 84
    assert data["range_start"] == "2026-09-21"
    assert data["events"] == [
        {"date": "2026-09-21", "kind": "annual_leave", "portion": "morning"},
        {"date": "2026-09-22", "kind": "annual_leave", "portion": "morning"},
        {"date": "2026-09-23", "kind": "overtime"},
    ]
    assert "id" not in str(data)
    assert "description" not in str(data)


@pytest.mark.asyncio
async def test_roster_card_month_endpoint_is_bounded_and_sanitized() -> None:
    class Engine:
        def duty(self, day, roster_id, unit_id):
            return SimpleNamespace(code="E" if day.day % 2 else "R")

    class Store:
        def records(self, kind):
            if kind == "annual_leave":
                return [
                    {
                        "id": "private-leave-id",
                        "start_date": "2027-02-02",
                        "number_of_days": 1,
                        "day_portion": "afternoon",
                        "description": "Must not be exposed",
                    }
                ]
            return [{"id": "private-overtime-id", "date": "2027-02-04"}]

    coordinator = SimpleNamespace(
        data={"roster_id": "non-core", "unit_id": "unit-b"},
        engine=Engine(),
        _configured=lambda duty: duty,
    )
    runtime = SimpleNamespace(coordinator=coordinator, store=Store())
    request = SimpleNamespace(
        query={"month": "2027-02"},
        app={"hass": SimpleNamespace(data={DOMAIN: {"entry": runtime}})},
    )

    response = await RosterCardView().get(request)
    data = json.loads(response.body)

    assert data["month"] == "2027-02"
    assert data["card_version"] == frontend.ROSTER_CARD_VERSION
    assert data["range_start"] == "2027-02-01"
    assert data["range_end"] == "2027-03-14"
    assert len(data["days"]) == 42
    assert data["events"] == [
        {"date": "2027-02-02", "kind": "annual_leave", "portion": "afternoon"},
        {"date": "2027-02-04", "kind": "overtime"},
    ]
    assert "private" not in str(data)


@pytest.mark.asyncio
async def test_roster_card_month_endpoint_rejects_invalid_month() -> None:
    request = SimpleNamespace(query={"month": "2027-2"}, app={"hass": None})

    response = await RosterCardView().get(request)

    assert response.status == 400


def test_compatibility_overtime_summary_declares_hours() -> None:
    sensor = object.__new__(CompatibilitySummarySensor)
    sensor.key = "overtime"
    sensor.coordinator = SimpleNamespace(data={"overtime": []})

    assert sensor.extra_state_attributes == {
        "entries": 0,
        "unit_of_measurement": "h",
    }


def test_card_ranges_calculate_historical_and_future_core_non_core_duties() -> None:
    class Store:
        def records(self, kind):
            return []

    engine = RosterEngine()
    for roster_id, unit_id, start in (
        ("core", "unit-a", date(2025, 1, 27)),
        ("non-core-2", "unit-b", date(2027, 2, 1)),
    ):
        coordinator = SimpleNamespace(
            data={"roster_id": roster_id, "unit_id": unit_id},
            engine=engine,
            _configured=lambda duty: duty,
        )
        data = roster_card_data_for_range(
            SimpleNamespace(coordinator=coordinator, store=Store()),
            start,
            start + timedelta(days=27),
        )
        assert len(data["days"]) == 28
        assert data["days"][0] == {
            "date": start.isoformat(),
            "duty": engine.duty(start, roster_id, unit_id).code,
        }

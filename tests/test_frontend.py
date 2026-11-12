from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import custom_components.shift_plus.frontend as frontend
from custom_components.shift_plus.const import DOMAIN
from custom_components.shift_plus.frontend import (
    FRONTEND_RESOURCE_URL,
    async_ensure_lovelace_resource,
    async_remove_frontend_resource,
)
from custom_components.shift_plus.sensor import _roster_card_data


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
    assert registered[0].url_path == FRONTEND_RESOURCE_URL
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
        {"date": "2026-09-21", "kind": "annual_leave"},
        {"date": "2026-09-22", "kind": "annual_leave"},
        {"date": "2026-09-23", "kind": "overtime"},
    ]
    assert "id" not in str(data)
    assert "description" not in str(data)

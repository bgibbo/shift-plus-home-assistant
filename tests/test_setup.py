from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import custom_components.shift_plus as integration
from custom_components.shift_plus.const import DOMAIN, PLATFORMS
from custom_components.shift_plus.roster.engine import RosterEngine


def _definitions() -> dict:
    return {
        "schema": "ie.shiftplus.rosters",
        "version": 1,
        "rosters": [
            {
                "id": "test",
                "anchor_date": "2026-01-01",
                "cycle_length": 1,
                "pattern_period": 1,
                "units": [
                    {
                        "id": "unit-a",
                        "days": [
                            {
                                "code": "R",
                                "category": "rest",
                                "mandatory_rest": False,
                                "operational_verification": False,
                            }
                        ],
                    }
                ],
            }
        ],
    }


class _Entry:
    entry_id = "entry-one"
    data = {}
    options = {}
    runtime_data = None

    def add_update_listener(self, listener):
        return listener

    def async_on_unload(self, callback):
        return None


class _Hass:
    def __init__(self, executor_result=None, executor_error=None):
        self.data = {DOMAIN: {}}
        self.config = SimpleNamespace(time_zone="UTC")
        self.config_entries = SimpleNamespace(
            async_forward_entry_setups=AsyncMock(),
        )
        self.executor_result = executor_result
        self.executor_error = executor_error
        self.executor_calls = []

    async def async_add_executor_job(self, target, *args):
        self.executor_calls.append((target, args))
        if self.executor_error:
            raise self.executor_error
        return self.executor_result


@pytest.mark.asyncio
async def test_setup_and_reload_load_rosters_in_executor(monkeypatch) -> None:
    definitions = _definitions()
    hass = _Hass(executor_result=definitions)
    entry = _Entry()
    stores = []
    coordinators = []

    class Store:
        paired_devices = {}

        def __init__(self, hass, entry_id):
            stores.append(self)

        async def async_load(self):
            return None

    class Coordinator:
        def __init__(self, hass, entry, store, engine):
            assert isinstance(engine, RosterEngine)
            assert engine.roster_ids == ("test",)
            coordinators.append(self)

        async def async_config_entry_first_refresh(self):
            return None

    monkeypatch.setattr(integration, "_migrate_pairing_status_entity", lambda *_: None)
    monkeypatch.setattr(integration, "ShiftPlusStore", Store)
    monkeypatch.setattr(integration, "ShiftPlusCoordinator", Coordinator)
    monkeypatch.setattr(integration, "PairingManager", lambda *args: object())

    assert await integration.async_setup_entry(hass, entry)
    hass.data[DOMAIN].pop(entry.entry_id)
    assert await integration.async_setup_entry(hass, entry)

    assert len(hass.executor_calls) == 2
    assert all(call[0] is RosterEngine.load_definitions for call in hass.executor_calls)
    assert len(stores) == len(coordinators) == 2
    assert hass.config_entries.async_forward_entry_setups.await_count == 2
    hass.config_entries.async_forward_entry_setups.assert_awaited_with(entry, PLATFORMS)


@pytest.mark.asyncio
async def test_roster_load_failure_does_not_register_partial_runtime(
    monkeypatch,
) -> None:
    hass = _Hass(executor_error=ValueError("invalid roster definitions"))
    entry = _Entry()

    class Store:
        def __init__(self, hass, entry_id):
            pass

        async def async_load(self):
            return None

    monkeypatch.setattr(integration, "_migrate_pairing_status_entity", lambda *_: None)
    monkeypatch.setattr(integration, "ShiftPlusStore", Store)

    with pytest.raises(ValueError, match="invalid roster definitions"):
        await integration.async_setup_entry(hass, entry)

    assert entry.entry_id not in hass.data[DOMAIN]
    hass.config_entries.async_forward_entry_setups.assert_not_awaited()

"""Durable Home Assistant storage for operational and replicated data."""

from __future__ import annotations

import asyncio
import base64
from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import LEGACY_PUBLIC_STORAGE_KEY, STORAGE_KEY, STORAGE_VERSION
from .sync import ReplicatedRecord, SyncState


class ShiftPlusStore:
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry_id}"
        )
        self._legacy_public_store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{LEGACY_PUBLIC_STORAGE_KEY}.{entry_id}"
        )
        self.transport_lock = asyncio.Lock()
        self.sync_status = "never_synced"
        self.sync_details: dict[str, Any] = {}
        self._extra: dict[str, Any] = {}
        self.sync = SyncState()
        self.paired_devices: dict[str, dict[str, Any]] = {}
        self.last_successful_sync: str | None = None
        self.sync_requested_at: str | None = None

    async def async_load(self) -> None:
        raw = await self._store.async_load()
        if raw is None:
            legacy = await self._legacy_public_store.async_load()
            raw = _migrate_public_501(legacy) if legacy else {}
            if legacy:
                await self._store.async_save(raw)
        raw = raw or {}
        self._extra = {
            key: value
            for key, value in raw.items()
            if key
            not in {
                "sync",
                "paired_devices",
                "last_successful_sync",
                "sync_requested_at",
                "sync_status",
                "sync_details",
            }
        }
        self.sync_status = raw.get("sync_status", "never_synced")
        self.sync_details = dict(raw.get("sync_details", {}))
        self.sync = SyncState(raw.get("sync"))
        self.paired_devices = dict(raw.get("paired_devices", {}))
        self.last_successful_sync = raw.get("last_successful_sync")
        self.sync_requested_at = raw.get("sync_requested_at")

    async def async_save(self) -> None:
        await self._store.async_save(
            {
                **self._extra,
                "sync_status": self.sync_status,
                "sync_details": self.sync_details,
                "sync": self.sync.to_dict(),
                "paired_devices": self.paired_devices,
                "last_successful_sync": self.last_successful_sync,
                "sync_requested_at": self.sync_requested_at,
            }
        )

    def records(self, record_type: str) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        for record in self.sync.records.values():
            if (
                record.record_type == record_type
                and not record.tombstone
                and record.payload
            ):
                values.append({"id": record.record_id, **record.payload})
        return values

    async def async_upsert(
        self, record_type: str, record_id: str, payload: dict[str, Any]
    ) -> None:
        self.sync.local_change(record_type, record_id, payload)
        await self.async_save()

    async def async_delete(self, record_type: str, record_id: str) -> None:
        self.sync.local_change(record_type, record_id, None, tombstone=True)
        await self.async_save()

    async def async_resolve_conflict(
        self, conflict_id: str, selection: str
    ) -> ReplicatedRecord:
        previous = deepcopy(self.sync.to_dict())
        try:
            record = self.sync.resolve_conflict_choice(conflict_id, selection)
            await self.async_save()
            return record
        except Exception:
            self.sync = SyncState(previous)
            raise

    async def async_merge(
        self, records: list[ReplicatedRecord], replica_id: str, ack: int
    ) -> list[dict[str, Any]]:
        previous = deepcopy(self.sync.to_dict())
        try:
            outcomes: list[dict[str, Any]] = []
            for record in records:
                outcome, accepted = self.sync.merge(record)
                outcomes.append(
                    {
                        "operation_id": record.operation_id,
                        "outcome": outcome,
                        "record": accepted.to_dict(),
                    }
                )
            self.sync.acknowledge(replica_id, ack)
            await self.async_save()
        except Exception:
            self.sync = SyncState(previous)
            raise
        return outcomes


def _migrate_public_501(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert the public 5.0.1 Store without changing protocol identities."""
    records = deepcopy(raw.get("records", {}))
    changes = deepcopy(raw.get("changes", []))
    devices: dict[str, dict[str, Any]] = {}
    for device_id, value in raw.get("devices", {}).items():
        credential = str(value["credential"])
        credential_bytes = base64.urlsafe_b64decode(
            credential + "=" * (-len(credential) % 4)
        )
        devices[device_id] = {
            "credential": base64.b64encode(credential_bytes).decode(),
            "claim_id": value.get("entitlement_jti"),
            "entitlement_id": value.get("entitlement_id"),
            "entitlement_issued_at": value.get("entitlement_issued_at", 0),
            "entitlement_jti": value.get("entitlement_jti"),
            "app_public_key": value["app_public_key"],
            "entitlement_expires_at": value["entitlement_expires_at"],
            "revoked": False,
            "used_nonces": [],
        }
    operations = {
        item.get("record", {}).get("operation_id")
        for item in changes
        if item.get("record", {}).get("operation_id")
    }
    return {
        "sync": {
            "replica_id": raw.get("replica_id"),
            "counter": 0,
            "cursor": int(raw.get("cursor", 0)),
            "records": records,
            "journal": changes,
            "seen_operations": sorted(operations),
            "conflicts": {},
            "replica_acks": {},
        },
        "paired_devices": devices,
        "last_successful_sync": None,
        "sync_requested_at": None,
        "sync_status": "migrated",
        "sync_details": {"source": "public_5.0.1"},
    }

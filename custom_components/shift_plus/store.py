"""Persistent protocol state for Shift Plus."""

from __future__ import annotations

import asyncio
import secrets
import uuid
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import MAX_OPERATIONS, PAIRING_TTL_SECONDS, STORE_KEY_PREFIX, STORE_VERSION
from .crypto import (
    b64decode,
    b64encode,
    derive_credential,
    validate_entitlement_renewal,
)


class ShiftPlusStore:
    """Own pairing sessions, devices and the replicated record log."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.entry_id = entry_id
        self._store: Store[dict[str, Any]] = Store(
            hass, STORE_VERSION, f"{STORE_KEY_PREFIX}.{entry_id}"
        )
        self._lock = asyncio.Lock()
        self._sessions: dict[str, dict[str, Any]] = {}
        self._seen_nonces: dict[str, dict[str, datetime]] = {}
        self._listeners: set[Callable[[], None]] = set()
        self.data: dict[str, Any] = {}

    async def async_load(self) -> None:
        """Load state and create the HA replica identity if needed."""
        loaded = await self._store.async_load()
        self.data = loaded or {
            "replica_id": f"ha-{uuid.uuid4()}",
            "server_key": b64encode(
                X25519PrivateKey.generate().private_bytes(
                    serialization.Encoding.Raw,
                    serialization.PrivateFormat.Raw,
                    serialization.NoEncryption(),
                )
            ),
            "devices": {},
            "records": {},
            "changes": [],
            "cursor": 0,
        }
        await self._store.async_save(self.data)

    @property
    def private_key(self) -> X25519PrivateKey:
        return X25519PrivateKey.from_private_bytes(b64decode(self.data["server_key"]))

    def new_pairing(self, base_url: str) -> dict[str, Any]:
        """Create a short-lived, single-use QR payload."""
        session_id = str(uuid.uuid4())
        one_time_secret = b64encode(secrets.token_bytes(32))
        expires_at = datetime.now(UTC) + timedelta(seconds=PAIRING_TTL_SECONDS)
        self._sessions[session_id] = {
            "one_time_secret": one_time_secret,
            "expires_at": expires_at,
        }
        public_key = self.private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return {
            "protocol": 1,
            "entry_id": self.entry_id,
            "base_url": base_url.rstrip("/"),
            "session_id": session_id,
            "one_time_secret": one_time_secret,
            "server_public_key": b64encode(public_key),
            "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        }

    def consume_pairing(self, session_id: str, one_time_secret: str) -> None:
        """Validate and consume a pairing session."""
        session = self._sessions.pop(session_id, None)
        if (
            session is None
            or session["expires_at"] <= datetime.now(UTC)
            or not secrets.compare_digest(session["one_time_secret"], one_time_secret)
        ):
            raise ValueError("Pairing session is invalid or expired")

    async def add_device(
        self,
        *,
        device_id: str,
        app_public_key: str,
        one_time_secret: str,
        entitlement_expires_at: datetime,
        entitlement_id: str,
        entitlement_issued_at: float,
        entitlement_jti: str,
    ) -> None:
        """Persist a paired device and its derived credential."""
        credential = derive_credential(
            self.private_key,
            app_public_key,
            one_time_secret,
            self.entry_id,
            device_id,
        )
        async with self._lock:
            self.data["devices"][device_id] = {
                "app_public_key": app_public_key,
                "credential": b64encode(credential),
                "entitlement_expires_at": entitlement_expires_at.isoformat(),
                "entitlement_id": entitlement_id,
                "entitlement_issued_at": entitlement_issued_at,
                "entitlement_jti": entitlement_jti,
            }
            await self._store.async_save(self.data)
        self._notify()

    def device(self, device_id: str) -> dict[str, Any] | None:
        return self.data["devices"].get(device_id)

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Notify entities when synchronized state changes."""
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    def accept_nonce(self, device_id: str, nonce: str) -> bool:
        """Reject replayed nonces while bounding memory use."""
        now = datetime.now(UTC)
        seen = self._seen_nonces.setdefault(device_id, {})
        cutoff = now - timedelta(minutes=10)
        for old_nonce in [key for key, value in seen.items() if value < cutoff]:
            del seen[old_nonce]
        if nonce in seen:
            return False
        seen[nonce] = now
        return True

    async def sync(
        self, operations: list[dict[str, Any]], cursor: int
    ) -> dict[str, Any]:
        """Merge client operations and return changes after its cursor."""
        if len(operations) > MAX_OPERATIONS:
            raise ValueError("Too many operations")
        outcomes: list[dict[str, Any]] = []
        async with self._lock:
            for operation in operations:
                self._validate_record(operation)
                operation_id = operation["operation_id"]
                if any(
                    item["record"].get("operation_id") == operation_id
                    for item in self.data["changes"]
                ):
                    outcomes.append(
                        {"operation_id": operation_id, "status": "duplicate"}
                    )
                    continue
                storage_key = f"{operation['record_type']}:{operation['record_id']}"
                current = self.data["records"].get(storage_key)
                winner = self._winner(current, operation)
                if winner is operation:
                    self.data["records"][storage_key] = deepcopy(operation)
                    self.data["cursor"] += 1
                    self.data["changes"].append(
                        {"cursor": self.data["cursor"], "record": deepcopy(operation)}
                    )
                outcomes.append({"operation_id": operation_id, "status": "accepted"})
            changes = [
                deepcopy(item)
                for item in self.data["changes"]
                if item["cursor"] > cursor
            ][:MAX_OPERATIONS]
            await self._store.async_save(self.data)
        self._notify()
        return {
            "outcomes": outcomes,
            "changes": changes,
            "server_cursor": self.data["cursor"],
        }

    async def update_entitlement(
        self,
        device_id: str,
        expires_at: datetime,
        *,
        entitlement_id: str,
        issued_at: float,
        jti: str,
    ) -> None:
        async with self._lock:
            device = self.data["devices"][device_id]
            validate_entitlement_renewal(
                device, entitlement_id=entitlement_id, issued_at=issued_at
            )
            device["entitlement_expires_at"] = expires_at.isoformat()
            device["entitlement_id"] = entitlement_id
            device["entitlement_issued_at"] = issued_at
            device["entitlement_jti"] = jti
            await self._store.async_save(self.data)
        self._notify()

    async def revoke(self, device_id: str) -> None:
        async with self._lock:
            self.data["devices"].pop(device_id, None)
            self._seen_nonces.pop(device_id, None)
            await self._store.async_save(self.data)
        self._notify()

    @staticmethod
    def _validate_record(record: dict[str, Any]) -> None:
        required = {
            "record_type": str,
            "record_id": str,
            "version": dict,
            "origin_replica_id": str,
            "origin_counter": int,
            "tombstone": bool,
            "operation_id": str,
        }
        if any(not isinstance(record.get(key), kind) for key, kind in required.items()):
            raise ValueError("Malformed sync record")
        if not record["tombstone"] and not isinstance(record.get("payload"), dict):
            raise ValueError("Live records require a payload")

    @classmethod
    def _winner(
        cls, current: dict[str, Any] | None, incoming: dict[str, Any]
    ) -> dict[str, Any]:
        if current is None:
            return incoming
        relation = cls._compare_versions(incoming["version"], current["version"])
        if relation == 1:
            return incoming
        if relation == -1 or relation == 0:
            return current
        incoming_key = (incoming["origin_counter"], incoming["origin_replica_id"])
        current_key = (current["origin_counter"], current["origin_replica_id"])
        return incoming if incoming_key > current_key else current

    @staticmethod
    def _compare_versions(first: dict[str, int], second: dict[str, int]) -> int | None:
        first_greater = second_greater = False
        for key in set(first) | set(second):
            first_value, second_value = first.get(key, 0), second.get(key, 0)
            first_greater |= first_value > second_value
            second_greater |= second_value > first_value
        if first_greater and second_greater:
            return None
        if first_greater:
            return 1
        if second_greater:
            return -1
        return 0

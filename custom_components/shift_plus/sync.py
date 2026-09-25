"""Offline-first replicated record and journal primitives."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class VersionRelation(Enum):
    EQUAL = "equal"
    DOMINATES = "dominates"
    DOMINATED = "dominated"
    CONCURRENT = "concurrent"


def compare_vectors(first: dict[str, int], second: dict[str, int]) -> VersionRelation:
    keys = set(first) | set(second)
    first_greater = any(first.get(key, 0) > second.get(key, 0) for key in keys)
    second_greater = any(second.get(key, 0) > first.get(key, 0) for key in keys)
    if first_greater and second_greater:
        return VersionRelation.CONCURRENT
    if first_greater:
        return VersionRelation.DOMINATES
    if second_greater:
        return VersionRelation.DOMINATED
    return VersionRelation.EQUAL


@dataclass(slots=True)
class ReplicatedRecord:
    record_type: str
    record_id: str
    payload: dict[str, Any] | None
    version: dict[str, int]
    origin_replica_id: str
    origin_counter: int
    tombstone: bool = False
    operation_id: str = ""

    def __post_init__(self) -> None:
        if not self.operation_id:
            self.operation_id = str(uuid.uuid4())

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ReplicatedRecord:
        return cls(
            record_type=value["record_type"],
            record_id=value["record_id"],
            payload=value.get("payload"),
            version={str(key): int(item) for key, item in value["version"].items()},
            origin_replica_id=value["origin_replica_id"],
            origin_counter=int(value["origin_counter"]),
            tombstone=bool(value.get("tombstone", False)),
            operation_id=value["operation_id"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": self.record_type,
            "record_id": self.record_id,
            "payload": self.payload,
            "version": self.version,
            "origin_replica_id": self.origin_replica_id,
            "origin_counter": self.origin_counter,
            "tombstone": self.tombstone,
            "operation_id": self.operation_id,
        }


class SyncState:
    """Durable state machine serialisable into Home Assistant Store."""

    def __init__(self, raw: dict[str, Any] | None = None) -> None:
        raw = raw or {}
        self.replica_id = raw.get("replica_id") or f"ha-{uuid.uuid4()}"
        self.counter = int(raw.get("counter", 0))
        self.cursor = int(raw.get("cursor", 0))
        self.records: dict[str, ReplicatedRecord] = {
            key: ReplicatedRecord.from_dict(value)
            for key, value in raw.get("records", {}).items()
        }
        self.journal: list[dict[str, Any]] = list(raw.get("journal", []))
        self.seen_operations: set[str] = set(raw.get("seen_operations", []))
        self.conflicts: dict[str, dict[str, Any]] = dict(raw.get("conflicts", {}))
        self.replica_acks: dict[str, int] = {
            key: int(value) for key, value in raw.get("replica_acks", {}).items()
        }

    @staticmethod
    def key(record_type: str, record_id: str) -> str:
        return f"{record_type}:{record_id}"

    def local_change(
        self,
        record_type: str,
        record_id: str,
        payload: dict[str, Any] | None,
        *,
        tombstone: bool = False,
    ) -> ReplicatedRecord:
        key = self.key(record_type, record_id)
        existing = self.records.get(key)
        self.counter += 1
        version = dict(existing.version) if existing else {}
        version[self.replica_id] = self.counter
        record = ReplicatedRecord(
            record_type=record_type,
            record_id=record_id,
            payload=None if tombstone else payload,
            version=version,
            origin_replica_id=self.replica_id,
            origin_counter=self.counter,
            tombstone=tombstone,
        )
        self._accept(record)
        return record

    def merge(self, incoming: ReplicatedRecord) -> tuple[str, ReplicatedRecord]:
        if incoming.operation_id in self.seen_operations:
            return "duplicate", self.records[
                self.key(incoming.record_type, incoming.record_id)
            ]
        key = self.key(incoming.record_type, incoming.record_id)
        existing = self.records.get(key)
        if existing is None:
            self._accept(incoming)
            return "accepted", incoming
        relation = compare_vectors(incoming.version, existing.version)
        if relation is VersionRelation.DOMINATES:
            self._accept(incoming)
            return "accepted", incoming
        if relation in {VersionRelation.DOMINATED, VersionRelation.EQUAL}:
            self.seen_operations.add(incoming.operation_id)
            return "stale", existing

        winner, loser = sorted(
            (incoming, existing),
            key=lambda item: (
                item.origin_counter,
                item.origin_replica_id,
                item.operation_id,
            ),
            reverse=True,
        )
        self.conflicts[key] = {
            "winner": winner.to_dict(),
            "loser": loser.to_dict(),
            "detected_at": datetime.now(UTC).isoformat(),
        }
        self._accept(winner)
        self.seen_operations.add(loser.operation_id)
        return "conflict", winner

    def resolve_conflict(
        self, key: str, payload: dict[str, Any] | None, tombstone: bool = False
    ) -> ReplicatedRecord:
        conflict = self.conflicts.pop(key)
        vectors = [conflict["winner"]["version"], conflict["loser"]["version"]]
        merged: dict[str, int] = {}
        for vector in vectors:
            for replica, counter in vector.items():
                merged[replica] = max(merged.get(replica, 0), int(counter))
        record_type, record_id = key.split(":", 1)
        self.counter = max(self.counter, merged.get(self.replica_id, 0)) + 1
        merged[self.replica_id] = self.counter
        record = ReplicatedRecord(
            record_type=record_type,
            record_id=record_id,
            payload=None if tombstone else payload,
            version=merged,
            origin_replica_id=self.replica_id,
            origin_counter=self.counter,
            tombstone=tombstone,
        )
        self._accept(record)
        return record

    def changes_after(self, cursor: int, limit: int = 250) -> list[dict[str, Any]]:
        return [item for item in self.journal if int(item["cursor"]) > cursor][:limit]

    def acknowledge(self, replica_id: str, cursor: int) -> None:
        acknowledged = min(max(0, cursor), self.cursor)
        self.replica_acks[replica_id] = max(
            self.replica_acks.get(replica_id, 0), acknowledged
        )
        self.prune_acknowledged()

    @property
    def pending_change_count(self) -> int:
        """Journal entries still required by at least one known replica."""
        if not self.replica_acks:
            return len(self.journal)
        oldest_ack = min(self.replica_acks.values())
        return sum(int(item["cursor"]) > oldest_ack for item in self.journal)

    def prune_acknowledged(self) -> None:
        """Discard delivery history only after every known replica acknowledged it."""
        if not self.replica_acks:
            return
        oldest_ack = min(self.replica_acks.values())
        self.journal = [
            item for item in self.journal if int(item["cursor"]) > oldest_ack
        ]

    def _accept(self, record: ReplicatedRecord) -> None:
        self.cursor += 1
        self.records[self.key(record.record_type, record.record_id)] = record
        self.seen_operations.add(record.operation_id)
        self.journal.append({"cursor": self.cursor, "record": record.to_dict()})

    def to_dict(self) -> dict[str, Any]:
        return {
            "replica_id": self.replica_id,
            "counter": self.counter,
            "cursor": self.cursor,
            "records": {key: value.to_dict() for key, value in self.records.items()},
            "journal": self.journal,
            "seen_operations": sorted(self.seen_operations),
            "conflicts": self.conflicts,
            "replica_acks": self.replica_acks,
        }

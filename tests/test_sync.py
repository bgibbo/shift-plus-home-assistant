from custom_components.shift_plus.sync import (
    ReplicatedRecord,
    SyncState,
    VersionRelation,
    compare_vectors,
)


def test_version_vectors_detect_causality_and_concurrency() -> None:
    assert compare_vectors({"a": 2}, {"a": 1}) is VersionRelation.DOMINATES
    assert compare_vectors({"a": 1}, {"a": 1}) is VersionRelation.EQUAL
    assert compare_vectors({"a": 2}, {"a": 1, "b": 1}) is VersionRelation.CONCURRENT


def test_duplicate_operations_are_idempotent() -> None:
    state = SyncState({"replica_id": "ha"})
    record = ReplicatedRecord(
        "overtime", "one", {"date": "2026-08-09"}, {"phone": 1}, "phone", 1
    )
    assert state.merge(record)[0] == "accepted"
    assert state.merge(record)[0] == "duplicate"
    assert len(state.records) == 1


def test_concurrent_changes_converge_and_preserve_conflict() -> None:
    state = SyncState({"replica_id": "ha"})
    state.local_change("annual_leave", "leave", {"number_of_days": 1})
    incoming = ReplicatedRecord(
        "annual_leave",
        "leave",
        {"number_of_days": 2},
        {"phone": 1},
        "phone",
        1,
    )
    outcome, winner = state.merge(incoming)
    assert outcome == "conflict"
    assert "annual_leave:leave" in state.conflicts
    resolved = state.resolve_conflict("annual_leave:leave", {"number_of_days": 3})
    assert resolved.payload == {"number_of_days": 3}
    assert resolved.version["ha"] >= 2
    assert resolved.version["phone"] == 1


def test_tombstone_dominates_old_offline_copy() -> None:
    state = SyncState({"replica_id": "ha"})
    state.merge(
        ReplicatedRecord(
            "overtime", "one", {"date": "2026-08-09"}, {"phone": 1}, "phone", 1
        )
    )
    tombstone = state.local_change("overtime", "one", None, tombstone=True)
    stale = ReplicatedRecord(
        "overtime", "one", {"date": "2026-08-09"}, {"phone": 1}, "phone", 1
    )
    outcome, winner = state.merge(stale)
    assert outcome in {"stale", "duplicate"}
    assert winner.tombstone
    assert tombstone.tombstone


def test_round_trip_retains_acknowledgements_and_prunes_delivered_journal() -> None:
    state = SyncState({"replica_id": "ha"})
    state.local_change("overtime", "one", {"date": "2026-08-09"})
    state.acknowledge("phone", 1)
    restored = SyncState(state.to_dict())
    assert restored.replica_acks == {"phone": 1}
    assert restored.journal == []
    assert restored.pending_change_count == 0


def test_pending_count_only_includes_changes_not_acknowledged_by_every_replica() -> (
    None
):
    state = SyncState({"replica_id": "ha"})
    state.local_change("overtime", "one", {"date": "2026-08-09"})
    state.local_change("overtime", "two", {"date": "2026-08-10"})
    state.replica_acks = {"phone-a": 2, "phone-b": 1}
    assert state.pending_change_count == 1
    state.prune_acknowledged()
    assert [item["cursor"] for item in state.journal] == [2]


def test_offline_replica_prevents_unsafe_pruning_including_tombstones() -> None:
    state = SyncState({"replica_id": "ha"})
    state.local_change("overtime", "one", {"date": "2026-08-09"})
    tombstone = state.local_change("overtime", "one", None, tombstone=True)
    state.replica_acks = {"online-phone": 2, "offline-phone": 0}
    state.prune_acknowledged()
    assert len(state.journal) == 2
    assert state.pending_change_count == 2
    assert state.records["overtime:one"].tombstone
    assert tombstone.tombstone


def test_tombstone_record_survives_restart_after_safe_journal_pruning() -> None:
    state = SyncState({"replica_id": "ha"})
    state.local_change("overtime", "one", None, tombstone=True)
    state.acknowledge("phone", 1)
    restored = SyncState(state.to_dict())
    assert restored.journal == []
    assert restored.records["overtime:one"].tombstone


def test_acknowledgement_cannot_advance_beyond_server_cursor() -> None:
    state = SyncState({"replica_id": "ha"})
    state.local_change("overtime", "one", {"date": "2026-08-09"})
    state.acknowledge("phone", 999)
    assert state.replica_acks["phone"] == 1

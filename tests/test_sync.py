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


def _record(
    replica: str, counter: int, *, record_id: str = "record"
) -> ReplicatedRecord:
    return ReplicatedRecord(
        record_type="overtime",
        record_id=record_id,
        payload={
            "date": "2026-09-25",
            "start_minutes": 480,
            "finish_minutes": 600,
            "description": "private note",
            "credential": "must-not-appear",
        },
        version={replica: counter},
        origin_replica_id=replica,
        origin_counter=counter,
        operation_id=f"{replica}-{counter}-{record_id}",
    )


def test_android_operations_are_not_reported_as_outbound_ha_changes() -> None:
    state = SyncState({"replica_id": "ha"})
    state.merge(_record("android", 1))
    assert state.outbound_unacknowledged_count == 0
    assert state.journal_awaiting_ack_count == 1


def test_ha_change_and_cursor_acknowledgement_have_distinct_counts() -> None:
    state = SyncState({"replica_id": "ha", "replica_acks": {"android": 0}})
    state.local_change(
        "overtime",
        "ha-record",
        {"date": "2026-09-25", "start_minutes": 600, "finish_minutes": 660},
    )
    assert state.outbound_unacknowledged_count == 1
    assert state.journal_awaiting_ack_count == 1
    assert len(state.changes_after(0)) == 1
    assert state.outbound_unacknowledged_count == 1
    state.acknowledge("android", 1)
    assert state.outbound_unacknowledged_count == 0
    assert state.journal_awaiting_ack_count == 0


def _conflicted_state() -> SyncState:
    state = SyncState({"replica_id": "ha"})
    state.merge(_record("android-a", 1, record_id="one"))
    state.local_change(
        "overtime",
        "one",
        {"date": "2026-09-25", "start_minutes": 540, "finish_minutes": 660},
    )
    state.merge(
        ReplicatedRecord(
            "overtime",
            "one",
            {"date": "2026-09-25", "start_minutes": 720, "finish_minutes": 780},
            {"android-a": 2},
            "android-a",
            2,
            operation_id="concurrent-one",
        )
    )
    state.merge(_record("android-b", 1, record_id="two"))
    state.local_change(
        "overtime",
        "two",
        {"date": "2026-09-26", "start_minutes": 600, "finish_minutes": 700},
    )
    state.merge(
        ReplicatedRecord(
            "overtime",
            "two",
            {"date": "2026-09-26", "start_minutes": 800, "finish_minutes": 900},
            {"android-b": 2},
            "android-b",
            2,
            operation_id="concurrent-two",
        )
    )
    assert len(state.conflicts) == 2
    return state


def test_conflict_inspection_is_sanitized_and_survives_restart() -> None:
    restarted = SyncState(_conflicted_state().to_dict())
    summaries = restarted.conflict_summaries()
    assert len(summaries) == 2
    assert summaries[0]["record_type"] == "overtime"
    rendered = str(summaries)
    assert "private note" not in rendered
    assert "credential" not in rendered
    assert "android-a" not in rendered
    assert "app_public_key" not in rendered


def test_resolve_current_keeps_only_other_conflict_and_journals_result() -> None:
    state = _conflicted_state()
    selected = state.conflict_summaries()[0]
    current_values = selected["current"]["values"]
    cursor = state.cursor
    record = state.resolve_conflict_choice(selected["conflict_id"], "current")
    assert record.payload == current_values
    assert len(state.conflicts) == 1
    assert state.cursor == cursor + 1
    assert state.changes_after(cursor)[0]["record"] == record.to_dict()


def test_resolve_alternative_is_deliverable_to_android_protocol() -> None:
    state = _conflicted_state()
    selected = state.conflict_summaries()[0]
    alternative = selected["alternative"]["values"]
    cursor = state.cursor
    record = state.resolve_conflict_choice(selected["conflict_id"], "alternative")
    assert record.payload == alternative
    assert state.changes_after(cursor) == [
        {"cursor": cursor + 1, "record": record.to_dict()}
    ]
    assert record.origin_replica_id == "ha"
    assert len(record.version) >= 2

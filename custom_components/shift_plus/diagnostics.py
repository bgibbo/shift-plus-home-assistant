"""Privacy-preserving diagnostics."""

from homeassistant.components.diagnostics import async_redact_data


async def async_get_config_entry_diagnostics(hass, entry):
    runtime = entry.runtime_data
    return async_redact_data(
        {
            "config": {**entry.data, **entry.options},
            "roster_definition_version": runtime.coordinator.engine.definition_version,
            "record_counts": {
                "overtime": len(runtime.store.records("overtime")),
                "annual_leave": len(runtime.store.records("annual_leave")),
            },
            "paired_device_count": sum(
                not value.get("revoked")
                for value in runtime.store.paired_devices.values()
            ),
            "pending_journal_entries": runtime.store.sync.pending_change_count,
            "conflict_count": len(runtime.store.sync.conflicts),
            "last_successful_sync": runtime.store.last_successful_sync,
        },
        {"entitlement_public_key"},
    )

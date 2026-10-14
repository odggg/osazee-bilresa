"""Minimal diagnostics without Matter credentials. Author: OSAZEE."""
async def async_get_config_entry_diagnostics(hass, entry):
    bridge = entry.runtime_data
    return {"author": "OSAZEE", "version": "0.1.0b1",
            "connected_matter_entries": list(bridge.connections),
            "mapped_entities": {key: list(bridge.entities(key).values()) for key in bridge.connections},
            "emitted_since_setup": bridge.emitted, "last_event": bridge.last_event,
            "recognition": "Fresh aborted multipress; at least three presses, not exact count"}

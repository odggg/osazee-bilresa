"""OSAZEE BILRESA live Matter event bridge."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import re

from homeassistant.config_entries import ConfigEntry, ConfigEntryState, SIGNAL_CONFIG_ENTRY_CHANGED
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
from matter_server.common.models import EventType

from .detector import Detector

DOMAIN = "osazee_bilresa"
EVENT = "osazee_bilresa_multipress_aborted"
_LOGGER = logging.getLogger(__name__)
_ID = re.compile(r"-([0-9a-fA-F]{16})-MatterNodeDevice-([12])-GenericSwitch-59-1$")


class Bridge:
    """Subscribe to the existing Matter client without modifying it."""

    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.connections = {}
        self.lock = asyncio.Lock()
        self.closed = False
        self.emitted = 0
        self.last_event = None

    def entities(self, matter_entry_id):
        registry, devices = er.async_get(self.hass), dr.async_get(self.hass)
        mapped = {}
        for entity in er.async_entries_for_config_entry(registry, matter_entry_id):
            if entity.platform != "matter" or entity.disabled_by or not entity.entity_id.startswith("event."):
                continue
            device = devices.async_get(entity.device_id) if entity.device_id else None
            if not device or "BILRESA" not in (device.model or "").upper() or "IKEA" not in (device.manufacturer or "").upper():
                continue
            if match := _ID.search(entity.unique_id):
                mapped[(int(match[1], 16), int(match[2]))] = entity.entity_id
        # Exclude single-endpoint devices and the scroll-wheel model.
        return {key: value for key, value in mapped.items()
                if (key[0], 1) in mapped and (key[0], 2) in mapped}

    async def reconcile(self, *_):
        async with self.lock:
            if self.closed:
                return
            loaded = {}
            for matter_entry in self.hass.config_entries.async_entries("matter"):
                runtime = getattr(matter_entry, "runtime_data", None)
                if matter_entry.state is ConfigEntryState.LOADED and runtime is not None:
                    loaded[matter_entry.entry_id] = runtime.adapter.matter_client
            for entry_id, connection in list(self.connections.items()):
                if loaded.get(entry_id) is not connection["client"]:
                    for unsubscribe in connection["unsubscribe"]:
                        unsubscribe()
                    del self.connections[entry_id]
            for entry_id, client in loaded.items():
                if entry_id in self.connections:
                    continue
                detector = Detector()
                try:
                    # Historical events establish a floor only. They are NEVER dispatched.
                    async with asyncio.timeout(15):
                        diagnostics = await client.get_diagnostics()
                    detector.seed(diagnostics.events)
                except Exception as err:
                    _LOGGER.warning("Cannot establish a replay-safe Matter baseline: %s", err)
                    continue
                if self.closed:
                    return

                @callback
                def receive(event_type, event, *, detector=detector, entry_id=entry_id, client=client):
                    current = self.connections.get(entry_id)
                    if current is None or current["client"] is not client:
                        return
                    if event_type is not EventType.NODE_EVENT:
                        node_id = getattr(event, "node_id", event if isinstance(event, int) else None)
                        if node_id is not None:
                            detector.reset_node(node_id)
                        return
                    mapping = self.entities(entry_id)
                    entity_id = mapping.get((event.node_id, event.endpoint_id))
                    active = self.hass.is_running and entity_id is not None
                    if not detector.feed(event, self.hass.loop.time(), active=active):
                        return
                    data = {"entity_id": entity_id, "event_type": "multi_press_aborted",
                            "presses_at_least": 3, "node_id": event.node_id,
                            "endpoint_id": event.endpoint_id, "event_number": event.event_number,
                            "config_entry_id": entry_id}
                    self.emitted += 1
                    self.last_event = dict(data)
                    self.hass.bus.async_fire(EVENT, data)
                    _LOGGER.debug("Dispatched one fresh BILRESA aborted multipress: %s", data)

                unsubscribe = [
                    client.subscribe_events(receive, event_filter=EventType.NODE_EVENT),
                    client.subscribe_events(receive, event_filter=EventType.NODE_UPDATED),
                    client.subscribe_events(receive, event_filter=EventType.NODE_REMOVED),
                ]
                self.connections[entry_id] = {"client": client, "detector": detector, "unsubscribe": unsubscribe}
                _LOGGER.info("BILRESA bridge subscribed; historical events will not be replayed")

    @callback
    def changed(self, _change, changed_entry):
        if changed_entry.domain == "matter" and not self.closed:
            self.entry.async_create_background_task(self.hass, self.reconcile(), "Reconnect BILRESA Matter bridge")

    @callback
    def close(self):
        self.closed = True
        for connection in self.connections.values():
            for unsubscribe in connection["unsubscribe"]:
                unsubscribe()
        self.connections.clear()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Connect the bridge; all gesture actions remain in the blueprint."""
    bridge = Bridge(hass, entry)
    await bridge.reconcile()
    if not bridge.connections:
        raise ConfigEntryNotReady("A loaded Matter integration and diagnostics baseline are required")
    entry.runtime_data = bridge
    entry.async_on_unload(bridge.close)
    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_CONFIG_ENTRY_CHANGED, bridge.changed))
    # Fallback watches only the local client reference, not devices or network state.
    entry.async_on_unload(async_track_time_interval(hass, bridge.reconcile, timedelta(seconds=30)))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Release subscriptions without changing Matter or any device."""
    return True

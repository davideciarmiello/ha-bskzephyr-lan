from __future__ import annotations

from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import *

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    api = coordinator.api

    return serialize({
        "coordinator_data": coordinator.data,
        "raw_data": api._raw_data
    })



def serialize(obj):
    from datetime import datetime
    """Convert dict, list, BaseModel into JSON-serializable structures."""
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize(v) for v in obj]
    elif hasattr(obj, "dict"):
        return serialize(obj.dict())  # ricorsivo anche dentro BaseModel annidati
    elif isinstance(obj, datetime):
        return obj.isoformat()  # datetime → string ISO
    else:
        return obj
"""Minimal Home Assistant stubs used by the unit tests."""

from __future__ import annotations

import re
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import voluptuous as vol


class HomeAssistant:
    """Typing stub for Home Assistant."""


class ServiceCall:
    """Small service-call stand-in."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data


class ConfigEntry:
    """Typing stub for a config entry."""


class ConfigFlow:
    """Small config-flow stand-in."""

    def __init_subclass__(cls, *, domain: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.domain = domain

    def __init__(self) -> None:
        self.current_entries: list[ConfigEntry] = []

    def _async_current_entries(self) -> list[ConfigEntry]:
        return self.current_entries

    def async_abort(self, *, reason: str) -> dict[str, Any]:
        return {"type": "abort", "reason": reason}

    def async_create_entry(self, *, title: str, data: dict[str, Any]) -> dict[str, Any]:
        return {"type": "create_entry", "title": title, "data": data}

    def async_show_form(self, *, step_id: str, data_schema: Any) -> dict[str, Any]:
        return {"type": "form", "step_id": step_id, "data_schema": data_schema}


def _string(value: Any) -> str:
    if not isinstance(value, str):
        raise vol.Invalid("value must be a string")
    return value


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    raise vol.Invalid("value must be a boolean")


def _entity_id(value: Any) -> str:
    value = _string(value)
    if not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", value):
        raise vol.Invalid("invalid entity ID")
    return value


homeassistant = ModuleType("homeassistant")
config_entries = ModuleType("homeassistant.config_entries")
core = ModuleType("homeassistant.core")
helpers = ModuleType("homeassistant.helpers")
config_validation = ModuleType("homeassistant.helpers.config_validation")
config_entries.ConfigEntry = ConfigEntry
config_entries.ConfigFlow = ConfigFlow
core.HomeAssistant = HomeAssistant
core.ServiceCall = ServiceCall
config_validation.string = _string
config_validation.boolean = _boolean
config_validation.entity_id = _entity_id
helpers.config_validation = config_validation
homeassistant.config_entries = config_entries
homeassistant.core = core
homeassistant.helpers = helpers
sys.modules.setdefault("homeassistant", homeassistant)
sys.modules.setdefault("homeassistant.config_entries", config_entries)
sys.modules.setdefault("homeassistant.core", core)
sys.modules.setdefault("homeassistant.helpers", helpers)
sys.modules.setdefault("homeassistant.helpers.config_validation", config_validation)


def make_service_call(data: dict[str, Any]) -> Any:
    """Create a service call object for a registered handler."""
    return SimpleNamespace(data=data)

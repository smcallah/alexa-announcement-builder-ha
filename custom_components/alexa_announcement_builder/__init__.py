"""Alexa Announcement Builder integration."""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_BREAK_AFTER_MS,
    ATTR_BREAK_BEFORE_MS,
    ATTR_EMOTION,
    ATTR_EMOTION_INTENSITY,
    ATTR_MODE,
    ATTR_PITCH,
    ATTR_RATE,
    ATTR_RAW_SSML,
    ATTR_SPEECH_DOMAIN,
    ATTR_TARGET,
    ATTR_TEXT,
    ATTR_VOICE_MODE,
    ATTR_VOICE_NAME,
    ATTR_VOLUME,
    ATTR_WHISPER,
    DEFAULT_MODE,
    DEFAULT_VOICE_MODE,
    DOMAIN,
    EMOTION_INTENSITIES,
    EMOTIONS,
    MODES,
    PITCHES,
    RATES,
    SERVICE_SEND,
    SPEECH_DOMAINS,
    VOICE_MODES,
    VOLUMES,
)
from .ssml import build_ssml

_LOGGER = logging.getLogger(__name__)
_PERCENT_PATTERN = re.compile(r"^[1-9]\d*%$")
_SIGNED_PERCENT_PATTERN = re.compile(r"^[+-](?:0|[1-9]\d*)%$")


def _notify_entity_id(value: Any) -> str:
    """Validate that a value is a notify entity ID."""
    entity_id = cv.entity_id(value)
    if not entity_id.startswith("notify."):
        raise vol.Invalid("target must be a notify entity ID")
    return entity_id


def _rate(value: Any) -> str:
    """Validate an Alexa prosody rate."""
    value = cv.string(value)
    if value not in RATES and not _PERCENT_PATTERN.fullmatch(value):
        raise vol.Invalid("rate must be a named rate or a positive percentage")
    return value


def _pitch(value: Any) -> str:
    """Validate an Alexa prosody pitch."""
    value = cv.string(value)
    if value not in PITCHES and not _SIGNED_PERCENT_PATTERN.fullmatch(value):
        raise vol.Invalid("pitch must be a named pitch or a signed percentage")
    return value


def _validate_message(data: dict[str, Any]) -> dict[str, Any]:
    """Validate conditional message and voice fields."""
    if not data.get(ATTR_TEXT) and not data.get(ATTR_RAW_SSML):
        raise vol.Invalid("one of text or raw_ssml is required")
    if data.get(ATTR_RAW_SSML):
        return data
    if data[ATTR_VOICE_MODE] == "named_voice" and not data.get(ATTR_VOICE_NAME):
        raise vol.Invalid("voice_name is required when voice_mode is named_voice")
    if data[ATTR_VOICE_MODE] != "named_voice" and ATTR_VOICE_NAME in data:
        raise vol.Invalid("voice_name is only valid when voice_mode is named_voice")
    return data


SEND_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_TARGET): _notify_entity_id,
            vol.Optional(ATTR_TEXT): cv.string,
            vol.Optional(ATTR_MODE, default=DEFAULT_MODE): vol.In(MODES),
            vol.Optional(ATTR_VOICE_MODE, default=DEFAULT_VOICE_MODE): vol.In(
                VOICE_MODES
            ),
            vol.Optional(ATTR_VOICE_NAME): cv.string,
            vol.Optional(ATTR_RATE): _rate,
            vol.Optional(ATTR_PITCH): _pitch,
            vol.Optional(ATTR_VOLUME): vol.In(VOLUMES),
            vol.Optional(ATTR_WHISPER, default=False): cv.boolean,
            vol.Optional(ATTR_EMOTION): vol.In(EMOTIONS),
            vol.Optional(ATTR_EMOTION_INTENSITY): vol.In(EMOTION_INTENSITIES),
            vol.Optional(ATTR_SPEECH_DOMAIN): vol.In(SPEECH_DOMAINS),
            vol.Optional(ATTR_BREAK_BEFORE_MS): vol.All(
                vol.Coerce(int), vol.Range(min=0)
            ),
            vol.Optional(ATTR_BREAK_AFTER_MS): vol.All(
                vol.Coerce(int), vol.Range(min=0)
            ),
            vol.Optional(ATTR_RAW_SSML): cv.string,
        },
        extra=vol.PREVENT_EXTRA,
    ),
    _validate_message,
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up Alexa Announcement Builder and register its send action."""

    async def async_send(call: ServiceCall) -> None:
        target = call.data[ATTR_TARGET]
        message = build_ssml(call.data)
        _LOGGER.debug("Sending generated Alexa SSML to %s", target)
        await hass.services.async_call(
            "notify",
            "send_message",
            {"message": message},
            target={"entity_id": target},
            blocking=True,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND,
        async_send,
        schema=SEND_SCHEMA,
    )
    _LOGGER.info("Alexa Announcement Builder service registered")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Alexa Announcement Builder from a config entry."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Alexa Announcement Builder config entry."""
    return True

"""Alexa Announcement Builder integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
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
    ATTR_PITCH,
    ATTR_RATE,
    ATTR_RAW_SSML,
    ATTR_SPEECH_DOMAIN,
    ATTR_TARGET,
    ATTR_TEXT,
    ATTR_VOICE,
    ATTR_VOLUME,
    ATTR_WHISPER,
    DOMAIN,
    EMOTION_INTENSITIES,
    EMOTIONS,
    PITCHES,
    RATES,
    SERVICE_SEND,
    SPEECH_DOMAINS,
    VOICE_CHOICES,
    VOLUMES,
)
from .ssml import build_ssml

_LOGGER = logging.getLogger(__name__)

ACTIVE_CHOICE = "active_choice"
NAMED_RATE_CHOICE = "Named rate"
NAMED_PITCH_CHOICE = "Named pitch"
NAMED_VOLUME_CHOICE = "Named volume"
PERCENTAGE_CHOICE = "Enter %-age"
DB_ADJUSTMENT_CHOICE = "Enter dB adjustment"


def _notify_entity_id(value: Any) -> str:
    """Validate that a value is a notify entity ID."""
    entity_id = cv.entity_id(value)
    if not entity_id.startswith("notify."):
        raise vol.Invalid("target must be a notify entity ID")
    return entity_id


def _format_number(value: Decimal) -> str:
    """Format a decimal without exponent notation or unnecessary trailing zeros."""
    formatted = format(value, "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted


def _prosody_value(
    value: Any,
    *,
    named_choice: str,
    named_values: tuple[str, ...],
    custom_choice: str,
    minimum: Decimal,
    maximum: Decimal,
    suffix: str,
    signed: bool,
) -> str:
    """Validate and normalize a Home Assistant choose-selector value."""
    if not isinstance(value, Mapping):
        raise vol.Invalid("prosody value must come from its named or numeric selector")

    active_choice = value.get(ACTIVE_CHOICE)
    if active_choice == named_choice:
        selected = value.get(named_choice)
        if selected not in named_values:
            raise vol.Invalid(f"unsupported {named_choice.lower()}")
        return str(selected)

    if active_choice != custom_choice:
        raise vol.Invalid(f"select either {named_choice} or {custom_choice}")

    selected = value.get(custom_choice)
    if isinstance(selected, bool) or selected is None:
        raise vol.Invalid(f"{custom_choice} requires a number")
    try:
        number = Decimal(str(selected))
    except (InvalidOperation, ValueError):
        raise vol.Invalid(f"{custom_choice} requires a number") from None
    if not number.is_finite() or not minimum <= number <= maximum:
        raise vol.Invalid(f"{custom_choice} must be between {minimum} and {maximum}")

    formatted = _format_number(number)
    if signed and number >= 0:
        formatted = f"+{formatted}"
    return f"{formatted}{suffix}"


def _rate(value: Any) -> str:
    """Validate an Alexa prosody rate selector."""
    return _prosody_value(
        value,
        named_choice=NAMED_RATE_CHOICE,
        named_values=RATES,
        custom_choice=PERCENTAGE_CHOICE,
        minimum=Decimal("20"),
        maximum=Decimal("200"),
        suffix="%",
        signed=False,
    )


def _pitch(value: Any) -> str:
    """Validate an Alexa prosody pitch selector."""
    return _prosody_value(
        value,
        named_choice=NAMED_PITCH_CHOICE,
        named_values=PITCHES,
        custom_choice=PERCENTAGE_CHOICE,
        minimum=Decimal("-33.3"),
        maximum=Decimal("50"),
        suffix="%",
        signed=True,
    )


def _volume(value: Any) -> str:
    """Validate an Alexa prosody volume selector."""
    return _prosody_value(
        value,
        named_choice=NAMED_VOLUME_CHOICE,
        named_values=VOLUMES,
        custom_choice=DB_ADJUSTMENT_CHOICE,
        minimum=Decimal("-6"),
        maximum=Decimal("6"),
        suffix="dB",
        signed=True,
    )


def _validate_message(data: dict[str, Any]) -> dict[str, Any]:
    """Validate conditional message and voice fields."""
    if not data.get(ATTR_TEXT) and not data.get(ATTR_RAW_SSML):
        raise vol.Invalid("one of text or raw_ssml is required")
    return data


SEND_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_TARGET): _notify_entity_id,
            vol.Optional(ATTR_TEXT): cv.string,
            vol.Optional(ATTR_VOICE): vol.In(VOICE_CHOICES),
            vol.Optional(ATTR_RATE): _rate,
            vol.Optional(ATTR_PITCH): _pitch,
            vol.Optional(ATTR_VOLUME): _volume,
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

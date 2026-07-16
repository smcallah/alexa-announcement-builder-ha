"""Alexa Announcement Builder integration."""

from __future__ import annotations

import logging
import re
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
    ATTR_CONTENT,
    ATTR_CONTENT_TYPE,
    ATTR_EMOTION,
    ATTR_EMOTION_INTENSITY,
    ATTR_PITCH,
    ATTR_RATE,
    ATTR_RAW_SSML,
    ATTR_SEQUENCE,
    ATTR_SOUND,
    ATTR_SPEECH_DOMAIN,
    ATTR_TARGET,
    ATTR_TEXT,
    ATTR_VOICE,
    ATTR_VOLUME,
    ATTR_WHISPER,
    COMMON_SOUND_NAMES,
    COMMON_SOUNDS,
    DOMAIN,
    EMOTION_INTENSITIES,
    EMOTIONS,
    MAX_AUDIO_CLIPS_PER_MESSAGE,
    PITCHES,
    RATES,
    SERVICE_SEND,
    SPEECH_DOMAINS,
    VOICE_CHOICES,
    VOLUMES,
)
from .sound import normalize_sound_source
from .ssml import build_ssml

_LOGGER = logging.getLogger(__name__)
_ANNOUNCE_ENTITY_ID = re.compile(r"_announce(?:_\d+)?$")
_AUDIO_TAG = re.compile(r"<audio(?=\s|/?>)", re.IGNORECASE)

ACTIVE_CHOICE = "active_choice"
NAMED_RATE_CHOICE = "Named rate"
NAMED_PITCH_CHOICE = "Named pitch"
NAMED_VOLUME_CHOICE = "Named volume"
PERCENTAGE_CHOICE = "Enter %-age"
DB_ADJUSTMENT_CHOICE = "Enter dB adjustment"
COMMON_SOUND_CHOICE = "Common sound"
CUSTOM_SOUND_CHOICE = "Custom sound"
MESSAGE_CHOICE = "Message"
SOUND_CHOICE = "Sound"
RAW_SSML_CHOICE = "Raw SSML"


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


def _sound(value: Any) -> str:
    """Validate and normalize a Home Assistant sound choose-selector value."""
    if not isinstance(value, Mapping):
        raise vol.Invalid("sound must come from its common or custom selector")

    active_choice = value.get(ACTIVE_CHOICE)
    if active_choice == COMMON_SOUND_CHOICE:
        selected = value.get(COMMON_SOUND_CHOICE)
        if not isinstance(selected, str) or selected not in COMMON_SOUNDS:
            raise vol.Invalid("unsupported common sound")
        return COMMON_SOUNDS[selected]

    if active_choice != CUSTOM_SOUND_CHOICE:
        raise vol.Invalid(
            f"select either {COMMON_SOUND_CHOICE} or {CUSTOM_SOUND_CHOICE}"
        )
    return normalize_sound_source(value.get(CUSTOM_SOUND_CHOICE))


def _content_sound(value: Any) -> str:
    """Validate a preset key or custom source from the content sound selector."""
    if not isinstance(value, str):
        raise vol.Invalid("Sound requires a common sound or custom source")
    if value in COMMON_SOUNDS:
        return COMMON_SOUNDS[value]
    sound_key = next(
        (key for key, name in COMMON_SOUND_NAMES.items() if value == name), None
    )
    if sound_key is not None:
        return COMMON_SOUNDS[sound_key]
    return normalize_sound_source(value)


def _required_text(value: Any, field_name: str) -> str:
    """Validate a required, non-empty text value."""
    try:
        text = cv.string(value)
    except vol.Invalid:
        raise vol.Invalid(f"{field_name} is required") from None
    if not text.strip():
        raise vol.Invalid(f"{field_name} cannot be empty")
    return text


def _message_text(value: Any) -> str:
    """Validate required message text."""
    return _required_text(value, ATTR_TEXT)


MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TEXT): _message_text,
        vol.Optional(ATTR_VOICE): vol.In(VOICE_CHOICES),
        vol.Optional(ATTR_RATE): _rate,
        vol.Optional(ATTR_PITCH): _pitch,
        vol.Optional(ATTR_VOLUME): _volume,
        vol.Optional(ATTR_WHISPER): cv.boolean,
        vol.Optional(ATTR_EMOTION): vol.In(EMOTIONS),
        vol.Optional(ATTR_EMOTION_INTENSITY): vol.In(EMOTION_INTENSITIES),
        vol.Optional(ATTR_SPEECH_DOMAIN): vol.In(SPEECH_DOMAINS),
    },
    extra=vol.PREVENT_EXTRA,
)


def _content(value: Any) -> dict[str, Any]:
    """Validate and flatten the mutually exclusive content selector."""
    if not isinstance(value, Mapping):
        raise vol.Invalid("content must come from the content selector")

    active_choice = value.get(ACTIVE_CHOICE)
    if active_choice == MESSAGE_CHOICE:
        message = value.get(MESSAGE_CHOICE)
        if not isinstance(message, Mapping):
            raise vol.Invalid("Message requires message options")
        return dict(MESSAGE_SCHEMA(message))
    if active_choice == SOUND_CHOICE:
        return {ATTR_SOUND: _content_sound(value.get(SOUND_CHOICE))}
    if active_choice == RAW_SSML_CHOICE:
        return {
            ATTR_RAW_SSML: _required_text(value.get(RAW_SSML_CHOICE), ATTR_RAW_SSML)
        }
    raise vol.Invalid(f"select {MESSAGE_CHOICE}, {SOUND_CHOICE}, or {RAW_SSML_CHOICE}")


def _sequence(value: Any) -> list[dict[str, Any]]:
    """Validate and flatten an ordered list of sequence-selector items."""
    if not isinstance(value, list):
        raise vol.Invalid("sequence must come from the sequence selector")
    if not value:
        raise vol.Invalid("sequence must contain at least one item")

    normalized = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, Mapping):
            raise vol.Invalid(f"sequence item {index} must be an object")
        try:
            if set(item) == {ATTR_CONTENT}:
                # Keep automations created with the original nested selector valid.
                normalized.append(_content(item[ATTR_CONTENT]))
            else:
                normalized.append(_flat_sequence_item(item))
        except vol.Invalid as err:
            raise vol.Invalid(f"sequence item {index}: {err}") from err
    return normalized


_SEQUENCE_ITEM_FIELDS = {
    ATTR_CONTENT_TYPE,
    ATTR_TEXT,
    ATTR_SOUND,
    ATTR_RAW_SSML,
    ATTR_VOICE,
    ATTR_RATE,
    ATTR_PITCH,
    ATTR_VOLUME,
    ATTR_WHISPER,
    ATTR_EMOTION,
    ATTR_EMOTION_INTENSITY,
    ATTR_SPEECH_DOMAIN,
}
_MESSAGE_ITEM_FIELDS = _SEQUENCE_ITEM_FIELDS - {
    ATTR_CONTENT_TYPE,
    ATTR_SOUND,
    ATTR_RAW_SSML,
}


def _flat_sequence_item(value: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one item from the non-nested sequence editor."""
    extra = set(value) - _SEQUENCE_ITEM_FIELDS
    if extra:
        names = ", ".join(sorted(extra))
        raise vol.Invalid(f"unsupported fields: {names}")

    content_type = value.get(ATTR_CONTENT_TYPE)
    if content_type == MESSAGE_CHOICE:
        if not isinstance(value.get(ATTR_TEXT), str) or not value[ATTR_TEXT].strip():
            raise vol.Invalid("Message requires non-empty message text")
        message = {
            field: field_value
            for field, field_value in value.items()
            if field in _MESSAGE_ITEM_FIELDS
        }
        return dict(MESSAGE_SCHEMA(message))
    if content_type == SOUND_CHOICE:
        if not value.get(ATTR_SOUND):
            raise vol.Invalid("Sound requires a sound selection or custom source")
        return {ATTR_SOUND: _content_sound(value.get(ATTR_SOUND))}
    if content_type == RAW_SSML_CHOICE:
        if (
            not isinstance(value.get(ATTR_RAW_SSML), str)
            or not value[ATTR_RAW_SSML].strip()
        ):
            raise vol.Invalid("Raw SSML requires non-empty markup")
        return {ATTR_RAW_SSML: _required_text(value.get(ATTR_RAW_SSML), ATTR_RAW_SSML)}
    raise vol.Invalid(
        f"choose Content type: {MESSAGE_CHOICE}, {SOUND_CHOICE}, or {RAW_SSML_CHOICE}"
    )


_LEGACY_CONTENT_FIELDS = {
    ATTR_TEXT,
    ATTR_SOUND,
    ATTR_RAW_SSML,
    ATTR_VOICE,
    ATTR_RATE,
    ATTR_PITCH,
    ATTR_VOLUME,
    ATTR_WHISPER,
    ATTR_EMOTION,
    ATTR_EMOTION_INTENSITY,
    ATTR_SPEECH_DOMAIN,
}
_MESSAGE_ONLY_FIELDS = _LEGACY_CONTENT_FIELDS - {
    ATTR_TEXT,
    ATTR_SOUND,
    ATTR_RAW_SSML,
}


def _validate_audio_clip_limit(data: Mapping[str, Any]) -> None:
    """Reject payloads that exceed Amazon's audio-clip limit."""
    items = data.get(ATTR_SEQUENCE)
    if not isinstance(items, list):
        items = [data]

    audio_clips = sum(
        bool(item.get(ATTR_SOUND))
        + len(_AUDIO_TAG.findall(item.get(ATTR_RAW_SSML, "")))
        for item in items
    )
    if audio_clips > MAX_AUDIO_CLIPS_PER_MESSAGE:
        raise vol.Invalid(
            f"Alexa accepts at most {MAX_AUDIO_CLIPS_PER_MESSAGE} audio clips per "
            f"message; this request contains {audio_clips}"
        )


def _normalize_and_validate_content(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten new content data and validate legacy YAML combinations."""
    if ATTR_SEQUENCE in data:
        conflicts = ({ATTR_CONTENT} | _LEGACY_CONTENT_FIELDS).intersection(data)
        if conflicts:
            names = ", ".join(sorted(conflicts))
            raise vol.Invalid(
                f"sequence cannot be combined with single-content fields: {names}"
            )
        _validate_audio_clip_limit(data)
        if _ANNOUNCE_ENTITY_ID.search(data[ATTR_TARGET]) and any(
            item.get(ATTR_SOUND) for item in data[ATTR_SEQUENCE]
        ):
            raise vol.Invalid(
                "A sequence containing Sound requires an Alexa Devices Speak "
                "target; Announce targets only play the announcement chime"
            )
        return data

    if ATTR_CONTENT in data:
        conflicts = _LEGACY_CONTENT_FIELDS.intersection(data)
        if conflicts:
            names = ", ".join(sorted(conflicts))
            raise vol.Invalid(f"content cannot be combined with legacy fields: {names}")
        content = data.pop(ATTR_CONTENT)
        data.update(content)

    selected = [
        field for field in (ATTR_TEXT, ATTR_SOUND, ATTR_RAW_SSML) if data.get(field)
    ]
    if len(selected) != 1:
        raise vol.Invalid("select exactly one of Message, Sound, or Raw SSML")

    content_field = selected[0]
    if content_field != ATTR_TEXT:
        incompatible = _MESSAGE_ONLY_FIELDS.intersection(data)
        if incompatible:
            names = ", ".join(sorted(incompatible))
            raise vol.Invalid(
                f"{content_field} cannot be combined with message options: {names}"
            )

    if content_field == ATTR_SOUND and _ANNOUNCE_ENTITY_ID.search(data[ATTR_TARGET]):
        raise vol.Invalid(
            "Sound requires an Alexa Devices Speak target; Announce targets only "
            "play the announcement chime"
        )
    _validate_audio_clip_limit(data)
    return data


SEND_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_TARGET): _notify_entity_id,
            vol.Optional(ATTR_SEQUENCE): _sequence,
            vol.Optional(ATTR_CONTENT): _content,
            vol.Optional(ATTR_TEXT): cv.string,
            vol.Optional(ATTR_SOUND): _sound,
            vol.Optional(ATTR_VOICE): vol.In(VOICE_CHOICES),
            vol.Optional(ATTR_RATE): _rate,
            vol.Optional(ATTR_PITCH): _pitch,
            vol.Optional(ATTR_VOLUME): _volume,
            vol.Optional(ATTR_WHISPER): cv.boolean,
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
    _normalize_and_validate_content,
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

"""Alexa SSML generation helpers."""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Any

from .const import (
    ATTR_BREAK_AFTER_MS,
    ATTR_BREAK_BEFORE_MS,
    ATTR_EMOTION,
    ATTR_EMOTION_INTENSITY,
    ATTR_PITCH,
    ATTR_RATE,
    ATTR_RAW_SSML,
    ATTR_SEQUENCE,
    ATTR_SOUND,
    ATTR_SPEECH_DOMAIN,
    ATTR_TEXT,
    ATTR_VOICE,
    ATTR_VOLUME,
    ATTR_WHISPER,
    DEFAULT_EMOTION_INTENSITY,
    DEFAULT_VOICE,
    NAMED_VOICES,
    ORIGINAL_ALEXA_PREFIX,
)


def _build_content(data: Mapping[str, Any]) -> str:
    """Build one validated message, sound, or raw SSML item."""
    if raw_ssml := data.get(ATTR_RAW_SSML):
        return str(raw_ssml)

    sound = data.get(ATTR_SOUND)
    voice = data.get(ATTR_VOICE, DEFAULT_VOICE)
    if sound:
        body = f'<audio src="{escape(str(sound), quote=True)}"/>'
    else:
        body = escape(str(data[ATTR_TEXT]), quote=False)

        prosody_attributes = []
        for field in (ATTR_RATE, ATTR_PITCH, ATTR_VOLUME):
            if value := data.get(field):
                prosody_attributes.append(f'{field}="{escape(str(value), quote=True)}"')
        if prosody_attributes:
            body = f"<prosody {' '.join(prosody_attributes)}>{body}</prosody>"

        if data.get(ATTR_WHISPER, False):
            body = f'<amazon:effect name="whispered">{body}</amazon:effect>'

        if emotion := data.get(ATTR_EMOTION):
            intensity = data.get(ATTR_EMOTION_INTENSITY, DEFAULT_EMOTION_INTENSITY)
            body = (
                f'<amazon:emotion name="{emotion}" intensity="{intensity}">'
                f"{body}</amazon:emotion>"
            )

        if speech_domain := data.get(ATTR_SPEECH_DOMAIN):
            body = f'<amazon:domain name="{speech_domain}">{body}</amazon:domain>'

        if voice in NAMED_VOICES:
            escaped_voice_name = escape(str(voice), quote=True)
            body = f'<voice name="{escaped_voice_name}">{body}</voice>'

    parts = []
    if not sound and voice == "original_alexa":
        parts.append(ORIGINAL_ALEXA_PREFIX)
    parts.append(body)
    return "".join(parts)


def build_ssml(data: Mapping[str, Any]) -> str:
    """Build Alexa-compatible SSML contents from validated service data."""
    if ATTR_SEQUENCE in data:
        body = "".join(_build_content(item) for item in data[ATTR_SEQUENCE])
    else:
        if raw_ssml := data.get(ATTR_RAW_SSML):
            return str(raw_ssml)
        body = _build_content(data)

    parts = []
    if ATTR_BREAK_BEFORE_MS in data:
        break_before = data[ATTR_BREAK_BEFORE_MS]
        parts.append(f'<break time="{break_before}ms"/>')
    parts.append(body)
    if ATTR_BREAK_AFTER_MS in data:
        break_after = data[ATTR_BREAK_AFTER_MS]
        parts.append(f'<break time="{break_after}ms"/>')

    return "".join(parts)

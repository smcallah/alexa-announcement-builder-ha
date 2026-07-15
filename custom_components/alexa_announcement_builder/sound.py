"""Alexa sound-source parsing and validation helpers."""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urlsplit

import voluptuous as vol

MAX_SOUND_SOURCE_LENGTH = 2048
MAX_SOUND_INPUT_LENGTH = 4096
_CONTROL_OR_WHITESPACE = re.compile(r"[\x00-\x20\x7f]")
_SOUNDBANK_PATH = re.compile(r"/[A-Za-z0-9][A-Za-z0-9._/-]*")
_AUDIO_TAG = re.compile(
    r"""<audio\s+src\s*=\s*(?P<quote>["'])(?P<src>.*?)(?P=quote)\s*/>""",
    re.DOTALL,
)


def _extract_audio_tag_source(value: str) -> str:
    """Extract src from one copied Alexa audio tag."""
    if (match := _AUDIO_TAG.fullmatch(value)) is None:
        raise vol.Invalid('custom sound must contain only one <audio src="..."/> tag')
    return unescape(match.group("src")).strip()


def normalize_sound_source(value: object) -> str:
    """Normalize and validate an HTTPS or Alexa sound-library source."""
    if not isinstance(value, str):
        raise vol.Invalid("custom sound must be a string")

    source = value.strip()
    if len(source) > MAX_SOUND_INPUT_LENGTH:
        raise vol.Invalid("custom sound input is too long")
    if source.startswith("<"):
        source = _extract_audio_tag_source(source)

    if not source:
        raise vol.Invalid("custom sound cannot be empty")
    if len(source) > MAX_SOUND_SOURCE_LENGTH:
        raise vol.Invalid("custom sound is too long")
    if _CONTROL_OR_WHITESPACE.search(source):
        raise vol.Invalid(
            "custom sound URL cannot contain whitespace or control characters"
        )

    try:
        parsed = urlsplit(source)
    except ValueError as err:
        raise vol.Invalid("custom sound is not a valid URL") from err

    if parsed.scheme == "soundbank":
        path_segments = parsed.path.split("/")[1:]
        if (
            parsed.netloc != "soundlibrary"
            or not _SOUNDBANK_PATH.fullmatch(parsed.path)
            or any(segment in {"", ".", ".."} for segment in path_segments)
            or parsed.query
            or parsed.fragment
        ):
            raise vol.Invalid(
                "soundbank source must start with soundbank://soundlibrary/"
            )
        return source

    if parsed.scheme == "https":
        try:
            hostname = parsed.hostname
            _ = parsed.port
        except ValueError as err:
            raise vol.Invalid("custom HTTPS sound has an invalid host or port") from err
        if (
            not hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise vol.Invalid(
                "custom HTTPS sound requires a host and cannot include credentials "
                "or a fragment"
            )
        # Accessing parsed.port above validates a numeric, in-range port when supplied.
        return source

    raise vol.Invalid("custom sound must use https:// or soundbank://soundlibrary/")

"""Tests for Alexa SSML generation."""

import pytest
import voluptuous as vol

from custom_components.alexa_announcement_builder import SEND_SCHEMA
from custom_components.alexa_announcement_builder.ssml import build_ssml


def test_plain_alexa_plus_message() -> None:
    assert build_ssml({"text": "Hello world."}) == "Hello world."


def test_original_alexa_voice_prefix() -> None:
    assert (
        build_ssml(
            {
                "text": "This is a test.",
                "voice": "original_alexa",
                "rate": "x-slow",
            }
        )
        == '<voice name="Kendra"> </voice>'
        '<prosody rate="x-slow">This is a test.</prosody>'
    )


def test_named_voice() -> None:
    assert (
        build_ssml({"text": "Hello.", "voice": "Matthew"})
        == '<voice name="Matthew">Hello.</voice>'
    )


def test_prosody_options() -> None:
    assert (
        build_ssml(
            {"text": "Careful.", "rate": "80%", "pitch": "+20%", "volume": "loud"}
        )
        == '<prosody rate="80%" pitch="+20%" volume="loud">Careful.</prosody>'
    )


def test_whisper() -> None:
    assert build_ssml({"text": "Quiet.", "whisper": True}) == (
        '<amazon:effect name="whispered">Quiet.</amazon:effect>'
    )


def test_emotion() -> None:
    assert (
        build_ssml(
            {"text": "Great!", "emotion": "excited", "emotion_intensity": "high"}
        )
        == '<amazon:emotion name="excited" intensity="high">Great!</amazon:emotion>'
    )


def test_domain() -> None:
    assert build_ssml({"text": "Top story.", "domain": "news"}) == (
        '<amazon:domain name="news">Top story.</amazon:domain>'
    )


def test_break_before_and_after() -> None:
    assert (
        build_ssml({"text": "Hello.", "break_before_ms": 250, "break_after_ms": 500})
        == '<break time="250ms"/>Hello.<break time="500ms"/>'
    )


def test_explicit_zero_length_break() -> None:
    assert build_ssml({"text": "Hello.", "break_before_ms": 0}) == (
        '<break time="0ms"/>Hello.'
    )


def test_xml_escaping() -> None:
    assert build_ssml({"text": 'Fish & chips < pizza > soup "today"'}) == (
        'Fish &amp; chips &lt; pizza &gt; soup "today"'
    )


def test_raw_ssml_passthrough() -> None:
    raw = '<amazon:effect name="whispered">A & B</amazon:effect>'
    assert build_ssml({"raw_ssml": raw, "voice": "original_alexa"}) == raw


def test_all_wrappers_follow_documented_order() -> None:
    assert build_ssml(
        {
            "text": "Hello.",
            "voice": "Joanna",
            "rate": "slow",
            "whisper": True,
            "emotion": "excited",
            "domain": "conversational",
        }
    ) == (
        '<voice name="Joanna"><amazon:domain name="conversational">'
        '<amazon:emotion name="excited" intensity="medium">'
        '<amazon:effect name="whispered"><prosody rate="slow">Hello.</prosody>'
        "</amazon:effect></amazon:emotion></amazon:domain></voice>"
    )


def test_schema_rejects_unsupported_named_voice() -> None:
    with pytest.raises(vol.Invalid):
        SEND_SCHEMA(
            {
                "target": "notify.office_echo_speak",
                "text": "Hello.",
                "voice": "NotARealVoice",
            }
        )


def test_schema_accepts_raw_ssml_without_text() -> None:
    data = SEND_SCHEMA(
        {"target": "notify.office_echo_speak", "raw_ssml": '<break time="1s"/>'}
    )
    assert data["raw_ssml"] == '<break time="1s"/>'


def test_schema_normalizes_named_prosody_values() -> None:
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_speak",
            "text": "Hello.",
            "rate": {"active_choice": "Named rate", "Named rate": "fast"},
            "pitch": {"active_choice": "Named pitch", "Named pitch": "low"},
            "volume": {
                "active_choice": "Named volume",
                "Named volume": "x-loud",
            },
        }
    )

    assert data["rate"] == "fast"
    assert data["pitch"] == "low"
    assert data["volume"] == "x-loud"


def test_schema_normalizes_custom_prosody_values() -> None:
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_speak",
            "text": "Hello.",
            "rate": {"active_choice": "Enter %-age", "Enter %-age": 80.5},
            "pitch": {"active_choice": "Enter %-age", "Enter %-age": 20},
            "volume": {
                "active_choice": "Enter dB adjustment",
                "Enter dB adjustment": -3.0,
            },
        }
    )

    assert data["rate"] == "80.5%"
    assert data["pitch"] == "+20%"
    assert data["volume"] == "-3dB"
    assert build_ssml(data) == (
        '<prosody rate="80.5%" pitch="+20%" volume="-3dB">Hello.</prosody>'
    )


@pytest.mark.parametrize(
    ("field", "choice", "value", "expected"),
    [
        ("rate", "Enter %-age", 20, "20%"),
        ("rate", "Enter %-age", 200, "200%"),
        ("pitch", "Enter %-age", -33.3, "-33.3%"),
        ("pitch", "Enter %-age", 50, "+50%"),
        ("volume", "Enter dB adjustment", -6, "-6dB"),
        ("volume", "Enter dB adjustment", 6, "+6dB"),
    ],
)
def test_schema_accepts_custom_prosody_boundaries(
    field: str, choice: str, value: float, expected: str
) -> None:
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_speak",
            "text": "Hello.",
            field: {"active_choice": choice, choice: value},
        }
    )

    assert data[field] == expected


@pytest.mark.parametrize(
    ("field", "choice", "value"),
    [
        ("rate", "Enter %-age", 19.9),
        ("rate", "Enter %-age", 200.1),
        ("pitch", "Enter %-age", -33.4),
        ("pitch", "Enter %-age", 50.1),
        ("volume", "Enter dB adjustment", -6.1),
        ("volume", "Enter dB adjustment", 6.1),
    ],
)
def test_schema_rejects_custom_prosody_outside_bounds(
    field: str, choice: str, value: float
) -> None:
    with pytest.raises(vol.Invalid):
        SEND_SCHEMA(
            {
                "target": "notify.office_echo_speak",
                "text": "Hello.",
                field: {"active_choice": choice, choice: value},
            }
        )


def test_schema_rejects_unselected_or_invalid_prosody_input() -> None:
    for rate in (
        "80%",
        {"active_choice": "Named rate", "Named rate": "turbo"},
        {"active_choice": "Enter %-age"},
    ):
        with pytest.raises(vol.Invalid):
            SEND_SCHEMA(
                {
                    "target": "notify.office_echo_speak",
                    "text": "Hello.",
                    "rate": rate,
                }
            )


def test_raw_ssml_bypasses_voice_wrapping() -> None:
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_speak",
            "raw_ssml": '<break time="1s"/>',
            "voice": "Joanna",
        }
    )
    assert build_ssml(data) == '<break time="1s"/>'


@pytest.mark.parametrize("target", ["light.office", "not an entity"])
def test_schema_rejects_non_notify_target(target: str) -> None:
    with pytest.raises(vol.Invalid):
        SEND_SCHEMA({"target": target, "text": "Hello."})

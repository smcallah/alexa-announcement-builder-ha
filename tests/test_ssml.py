"""Tests for Alexa SSML generation."""

import pytest
import voluptuous as vol

from custom_components.alexa_announcement_builder import SEND_SCHEMA
from custom_components.alexa_announcement_builder.const import COMMON_SOUNDS
from custom_components.alexa_announcement_builder.sound import normalize_sound_source
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
    assert build_ssml({"raw_ssml": raw}) == raw


def test_common_sound() -> None:
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_speak",
            "sound": {
                "active_choice": "Common sound",
                "Common sound": "doorbell_chime",
            },
        }
    )

    assert data["sound"] == COMMON_SOUNDS["doorbell_chime"]
    assert build_ssml(data) == (
        '<audio src="soundbank://soundlibrary/home/amzn_sfx_doorbell_chime_01"/>'
    )


def test_content_message_flattens_only_the_active_choice() -> None:
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_speak",
            "content": {
                "active_choice": "Message",
                "Message": {"text": "Hello.", "voice": "Joanna"},
                "Sound": "doorbell_chime",
                "Raw SSML": '<break time="5s"/>',
            },
        }
    )

    assert data == {
        "target": "notify.office_echo_speak",
        "text": "Hello.",
        "voice": "Joanna",
    }
    assert build_ssml(data) == '<voice name="Joanna">Hello.</voice>'


def test_content_raw_ssml_flattens_only_the_active_choice() -> None:
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_speak",
            "content": {
                "active_choice": "Raw SSML",
                "Message": {"text": "Ignore me.", "voice": "Joanna"},
                "Raw SSML": '<break time="1s"/>',
            },
        }
    )

    assert data == {
        "target": "notify.office_echo_speak",
        "raw_ssml": '<break time="1s"/>',
    }
    assert build_ssml(data) == '<break time="1s"/>'


def test_content_sound_flattens_only_the_active_choice() -> None:
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_speak",
            "content": {
                "active_choice": "Sound",
                "Message": {"text": "Ignore me.", "voice": "Joanna"},
                "Sound": "doorbell_chime",
            },
        }
    )

    assert data == {
        "target": "notify.office_echo_speak",
        "sound": COMMON_SOUNDS["doorbell_chime"],
    }


def test_sequence_preserves_order_and_per_message_options() -> None:
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_speak",
            "sequence": [
                {
                    "content": {
                        "active_choice": "Message",
                        "Message": {"text": "First.", "voice": "Joanna"},
                    }
                },
                {
                    "content": {
                        "active_choice": "Sound",
                        "Sound": "door_knock",
                    }
                },
                {
                    "content": {
                        "active_choice": "Message",
                        "Message": {
                            "text": "Second.",
                            "voice": "original_alexa",
                            "rate": {
                                "active_choice": "Named rate",
                                "Named rate": "slow",
                            },
                        },
                    }
                },
                {
                    "content": {
                        "active_choice": "Raw SSML",
                        "Raw SSML": '<break time="1s"/>',
                    }
                },
            ],
            "break_before_ms": 100,
            "break_after_ms": 250,
        }
    )

    assert data == {
        "target": "notify.office_echo_speak",
        "sequence": [
            {"text": "First.", "voice": "Joanna"},
            {"sound": COMMON_SOUNDS["door_knock"]},
            {"text": "Second.", "voice": "original_alexa", "rate": "slow"},
            {"raw_ssml": '<break time="1s"/>'},
        ],
        "break_before_ms": 100,
        "break_after_ms": 250,
    }
    assert build_ssml(data) == (
        '<break time="100ms"/>'
        '<voice name="Joanna">First.</voice>'
        '<audio src="soundbank://soundlibrary/doors/doors_knocks/knocks_01"/>'
        '<voice name="Kendra"> </voice>'
        '<prosody rate="slow">Second.</prosody>'
        '<break time="1s"/>'
        '<break time="250ms"/>'
    )


def test_flat_sequence_selector_preserves_order_and_per_message_options() -> None:
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_speak",
            "sequence": [
                {
                    "content_type": "Message",
                    "text": "First.",
                    "voice": "Joanna",
                },
                {"content_type": "Sound", "sound": "Door knock"},
                {
                    "content_type": "Message",
                    "text": "Second.",
                    "voice": "original_alexa",
                    "rate": {
                        "active_choice": "Named rate",
                        "Named rate": "slow",
                    },
                },
                {"content_type": "Raw SSML", "raw_ssml": '<break time="1s"/>'},
            ],
        }
    )

    assert data["sequence"] == [
        {"text": "First.", "voice": "Joanna"},
        {"sound": COMMON_SOUNDS["door_knock"]},
        {"text": "Second.", "voice": "original_alexa", "rate": "slow"},
        {"raw_ssml": '<break time="1s"/>'},
    ]


def test_flat_sequence_content_type_ignores_inactive_fields() -> None:
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_speak",
            "sequence": [
                {
                    "content_type": "Sound",
                    "text": "Stale message.",
                    "sound": "Doorbell chime",
                    "raw_ssml": '<break time="5s"/>',
                    "voice": "Joanna",
                    "whisper": True,
                }
            ],
        }
    )

    assert data["sequence"] == [{"sound": COMMON_SOUNDS["doorbell_chime"]}]


def test_sequence_accepts_five_audio_clips_mixed_with_messages() -> None:
    audio_tag = (
        '<audio src="soundbank://soundlibrary/home/amzn_sfx_doorbell_chime_01"/>'
    )
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_speak",
            "sequence": [
                {"content_type": "Sound", "sound": "Door knock"},
                {"content_type": "Message", "text": "First message."},
                {"content_type": "Sound", "sound": "Applause"},
                {"content_type": "Message", "text": "Second message."},
                {"content_type": "Sound", "sound": "Thunder"},
                {
                    "content_type": "Raw SSML",
                    "raw_ssml": f"{audio_tag}{audio_tag}",
                },
            ],
        }
    )

    assert build_ssml(data).count("<audio ") == 5


@pytest.mark.parametrize(
    "sequence",
    [
        [{"content_type": "Sound", "sound": "Door knock"}] * 6,
        [
            *([{"content_type": "Sound", "sound": "Door knock"}] * 4),
            {
                "content_type": "Raw SSML",
                "raw_ssml": (
                    '<audio src="soundbank://soundlibrary/home/'
                    'amzn_sfx_doorbell_chime_01"/>'
                    '<AUDIO src="soundbank://soundlibrary/home/'
                    'amzn_sfx_doorbell_chime_01"></AUDIO>'
                ),
            },
        ],
    ],
)
def test_schema_rejects_more_than_five_audio_clips(sequence: list[dict]) -> None:
    with pytest.raises(vol.Invalid, match=r"at most 5 audio clips.*contains 6"):
        SEND_SCHEMA(
            {
                "target": "notify.office_echo_speak",
                "sequence": sequence,
            }
        )


def test_sequence_message_only_is_valid_for_announce_target() -> None:
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_announce",
            "sequence": [
                {
                    "content": {
                        "active_choice": "Message",
                        "Message": {"text": "Front door open."},
                    }
                },
                {
                    "content": {
                        "active_choice": "Message",
                        "Message": {"text": "Please close it.", "voice": "Matthew"},
                    }
                },
            ],
        }
    )

    assert build_ssml(data) == (
        'Front door open.<voice name="Matthew">Please close it.</voice>'
    )


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [
        (
            "soundbank://soundlibrary/air/fire_extinguisher/fire_extinguisher_04",
            "soundbank://soundlibrary/air/fire_extinguisher/fire_extinguisher_04",
        ),
        (
            "https://audio.example.test/chime.mp3",
            "https://audio.example.test/chime.mp3",
        ),
        (
            '<audio src="soundbank://soundlibrary/doors/doors_knocks/knocks_01"/>',
            "soundbank://soundlibrary/doors/doors_knocks/knocks_01",
        ),
    ],
)
def test_content_sound_accepts_a_custom_source_as_one_scalar_value(
    supplied: str, expected: str
) -> None:
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_speak",
            "content": {
                "active_choice": "Sound",
                "Sound": supplied,
            },
        }
    )

    assert data == {
        "target": "notify.office_echo_speak",
        "sound": expected,
    }


@pytest.mark.parametrize("source", COMMON_SOUNDS.values())
def test_every_common_sound_source_is_valid(source: str) -> None:
    assert normalize_sound_source(source) == source


def test_door_knock_preset_uses_current_sound_library_source() -> None:
    assert COMMON_SOUNDS["door_knock"] == (
        "soundbank://soundlibrary/doors/doors_knocks/knocks_01"
    )


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [
        (
            "soundbank://soundlibrary/air/fire_extinguisher/fire_extinguisher_04",
            "soundbank://soundlibrary/air/fire_extinguisher/fire_extinguisher_04",
        ),
        (
            '<audio src="soundbank://soundlibrary/air/fire_extinguisher/'
            'fire_extinguisher_04"/>',
            "soundbank://soundlibrary/air/fire_extinguisher/fire_extinguisher_04",
        ),
        (
            "<audio src='https://audio.example.test/chime.mp3?token=a&amp;b=2'/>",
            "https://audio.example.test/chime.mp3?token=a&b=2",
        ),
        (
            "  https://audio.example.test/chime.mp3?token=a&b=2  ",
            "https://audio.example.test/chime.mp3?token=a&b=2",
        ),
    ],
)
def test_custom_sound_sources(supplied: str, expected: str) -> None:
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_speak",
            "sound": {
                "active_choice": "Custom sound",
                "Custom sound": supplied,
            },
        }
    )

    assert data["sound"] == expected
    assert build_ssml(data) == (f'<audio src="{expected.replace("&", "&amp;")}"/>')


def test_sound_keeps_breaks() -> None:
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_speak",
            "content": {
                "active_choice": "Sound",
                "Sound": "applause",
            },
            "break_before_ms": 100,
            "break_after_ms": 250,
        }
    )

    assert build_ssml(data) == (
        '<break time="100ms"/>'
        '<audio src="soundbank://soundlibrary/human/amzn_sfx_crowd_applause_01"/>'
        '<break time="250ms"/>'
    )


@pytest.mark.parametrize(
    "supplied",
    [
        "",
        "http://audio.example.test/chime.mp3",
        "audio.example.test/chime.mp3",
        "https://user:secret@audio.example.test/chime.mp3",
        "https://audio.example.test/chime.mp3#fragment",
        "https://audio.example.test:invalid/chime.mp3",
        "https://audio.example.test/chime file.mp3",
        "soundbank://example.test/animals/bird_01",
        "soundbank://soundlibrary/",
        "soundbank://soundlibrary/animals/../bird_01",
        "soundbank://soundlibrary/animals//bird_01",
        "soundbank://soundlibrary/animals/./bird_01",
        "soundbank://soundlibrary/animals/bird_01?variant=2",
        "<audio/>",
        '<audio src="https://audio.example.test/chime.mp3" loop="1"/>',
        '<audio src="https://audio.example.test/chime.mp3">text</audio>',
        '<audio src="https://audio.example.test/chime.mp3"></audio>',
        '<speak><audio src="https://audio.example.test/chime.mp3"/></speak>',
        "x" * 2049,
        f'<audio src="https://audio.example.test/{"x" * 5000}.mp3"/>',
        None,
    ],
)
def test_schema_rejects_invalid_custom_sound(supplied: object) -> None:
    with pytest.raises(vol.Invalid):
        SEND_SCHEMA(
            {
                "target": "notify.office_echo_speak",
                "sound": {
                    "active_choice": "Custom sound",
                    "Custom sound": supplied,
                },
            }
        )


@pytest.mark.parametrize(
    "sound",
    [
        "doorbell_chime",
        {"active_choice": "Common sound", "Common sound": "unknown"},
        {"active_choice": "Common sound", "Common sound": []},
        {"active_choice": "Custom sound"},
        {"active_choice": "Unsupported choice"},
    ],
)
def test_schema_rejects_invalid_sound_selector(sound: object) -> None:
    with pytest.raises(vol.Invalid):
        SEND_SCHEMA({"target": "notify.office_echo_speak", "sound": sound})


@pytest.mark.parametrize("other_field", ["text", "raw_ssml"])
def test_schema_rejects_sound_combined_with_message_content(
    other_field: str,
) -> None:
    with pytest.raises(vol.Invalid):
        SEND_SCHEMA(
            {
                "target": "notify.office_echo_speak",
                "sound": {
                    "active_choice": "Common sound",
                    "Common sound": "doorbell_chime",
                },
                other_field: "Hello.",
            }
        )


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


def test_schema_rejects_raw_ssml_with_voice() -> None:
    with pytest.raises(vol.Invalid):
        SEND_SCHEMA(
            {
                "target": "notify.office_echo_speak",
                "raw_ssml": '<break time="1s"/>',
                "voice": "Joanna",
            }
        )


def test_schema_rejects_message_and_raw_ssml_together() -> None:
    with pytest.raises(vol.Invalid):
        SEND_SCHEMA(
            {
                "target": "notify.office_echo_speak",
                "text": "Hello.",
                "raw_ssml": '<break time="1s"/>',
            }
        )


def test_schema_rejects_sound_with_message_options() -> None:
    with pytest.raises(vol.Invalid):
        SEND_SCHEMA(
            {
                "target": "notify.office_echo_speak",
                "sound": {
                    "active_choice": "Common sound",
                    "Common sound": "doorbell_chime",
                },
                "voice": "Joanna",
            }
        )


@pytest.mark.parametrize(
    "target", ["notify.office_echo_announce", "notify.office_echo_announce_2"]
)
def test_schema_rejects_sound_sent_to_announce_target(target: str) -> None:
    with pytest.raises(vol.Invalid, match="Speak target"):
        SEND_SCHEMA(
            {
                "target": target,
                "content": {
                    "active_choice": "Sound",
                    "Sound": "doorbell_chime",
                },
            }
        )


def test_schema_rejects_sequence_with_sound_sent_to_announce_target() -> None:
    with pytest.raises(vol.Invalid, match="sequence containing Sound"):
        SEND_SCHEMA(
            {
                "target": "notify.office_echo_announce",
                "sequence": [
                    {
                        "content": {
                            "active_choice": "Message",
                            "Message": {"text": "Listen."},
                        }
                    },
                    {
                        "content": {
                            "active_choice": "Sound",
                            "Sound": "doorbell_chime",
                        }
                    },
                ],
            }
        )


@pytest.mark.parametrize(
    "sequence",
    [
        [],
        "Message",
        [{}],
        [{"content": {"active_choice": "Message"}}],
        [
            {
                "content": {
                    "active_choice": "Message",
                    "Message": {"text": "Hello."},
                },
                "extra": True,
            }
        ],
    ],
)
def test_schema_rejects_invalid_sequence(sequence: object) -> None:
    with pytest.raises(vol.Invalid):
        SEND_SCHEMA(
            {
                "target": "notify.office_echo_speak",
                "sequence": sequence,
            }
        )


@pytest.mark.parametrize(
    ("item", "error"),
    [
        ({}, "choose Content type"),
        ({"content_type": "Message"}, "Message requires non-empty message text"),
        (
            {"content_type": "Message", "text": "   "},
            "Message requires non-empty message text",
        ),
        (
            {"content_type": "Sound"},
            "Sound requires a sound selection or custom source",
        ),
        (
            {"content_type": "Raw SSML", "raw_ssml": ""},
            "Raw SSML requires non-empty markup",
        ),
    ],
)
def test_schema_explains_incomplete_native_sequence_items(
    item: dict, error: str
) -> None:
    with pytest.raises(vol.Invalid, match=error):
        SEND_SCHEMA(
            {
                "target": "notify.office_echo_speak",
                "sequence": [item],
            }
        )


@pytest.mark.parametrize("single_field", ["content", "text", "sound", "raw_ssml"])
def test_schema_rejects_sequence_mixed_with_single_content(
    single_field: str,
) -> None:
    value: object = "Legacy content."
    if single_field == "content":
        value = {
            "active_choice": "Message",
            "Message": {"text": "Single content."},
        }
    elif single_field == "sound":
        value = {
            "active_choice": "Common sound",
            "Common sound": "doorbell_chime",
        }

    with pytest.raises(vol.Invalid, match="single-content fields"):
        SEND_SCHEMA(
            {
                "target": "notify.office_echo_speak",
                "sequence": [
                    {
                        "content": {
                            "active_choice": "Message",
                            "Message": {"text": "Sequence content."},
                        }
                    }
                ],
                single_field: value,
            }
        )


def test_schema_rejects_content_selector_mixed_with_legacy_fields() -> None:
    with pytest.raises(vol.Invalid, match="legacy fields"):
        SEND_SCHEMA(
            {
                "target": "notify.office_echo_speak",
                "content": {
                    "active_choice": "Message",
                    "Message": {"text": "New message."},
                },
                "text": "Legacy message.",
            }
        )


@pytest.mark.parametrize(
    "content",
    [
        "Message",
        {"active_choice": "Message"},
        {"active_choice": "Message", "Message": {"text": "  "}},
        {"active_choice": "Raw SSML", "Raw SSML": ""},
        {"active_choice": "Unsupported"},
    ],
)
def test_schema_rejects_invalid_content_selector(content: object) -> None:
    with pytest.raises(vol.Invalid):
        SEND_SCHEMA({"target": "notify.office_echo_speak", "content": content})


@pytest.mark.parametrize("target", ["light.office", "not an entity"])
def test_schema_rejects_non_notify_target(target: str) -> None:
    with pytest.raises(vol.Invalid):
        SEND_SCHEMA({"target": target, "text": "Hello."})

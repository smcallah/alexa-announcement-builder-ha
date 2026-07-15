"""Tests for integration metadata files."""

import json
from pathlib import Path

import yaml

from custom_components.alexa_announcement_builder.const import (
    COMMON_SOUNDS,
    NAMED_VOICES,
)

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "alexa_announcement_builder"


def test_json_metadata_is_valid() -> None:
    for path in (INTEGRATION / "manifest.json", INTEGRATION / "strings.json"):
        assert json.loads(path.read_text(encoding="utf-8"))

    assert json.loads(
        (INTEGRATION / "translations" / "en.json").read_text(encoding="utf-8")
    )


def test_manifest_enables_config_flow() -> None:
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["config_flow"] is True


def test_service_metadata_describes_all_schema_fields() -> None:
    metadata = yaml.safe_load((INTEGRATION / "services.yaml").read_text("utf-8"))
    fields = metadata["send"]["fields"]
    assert set(fields) == {
        "target",
        "content",
        "break_before_ms",
        "break_after_ms",
    }


def test_service_translations_cover_every_field() -> None:
    metadata = yaml.safe_load((INTEGRATION / "services.yaml").read_text("utf-8"))
    expected_fields = set(metadata["send"]["fields"])

    for path in (INTEGRATION / "strings.json", INTEGRATION / "translations/en.json"):
        translated = json.loads(path.read_text(encoding="utf-8"))
        assert set(translated["services"]["send"]["fields"]) == expected_fields


def test_voice_selector_lists_every_supported_voice() -> None:
    metadata = yaml.safe_load((INTEGRATION / "services.yaml").read_text("utf-8"))
    choices = metadata["send"]["fields"]["content"]["selector"]["choose"]["choices"]
    message_fields = choices["Message"]["selector"]["object"]["fields"]
    selector = message_fields["voice"]["selector"]["select"]

    assert selector["mode"] == "dropdown"
    assert tuple(option["value"] for option in selector["options"]) == (
        "alexa_plus",
        "original_alexa",
        *NAMED_VOICES,
    )
    assert all("(" in option["label"] for option in selector["options"][2:])


def test_target_selector_only_lists_alexa_device_notify_entities() -> None:
    metadata = yaml.safe_load((INTEGRATION / "services.yaml").read_text("utf-8"))
    selector = metadata["send"]["fields"]["target"]["selector"]["entity"]

    assert selector == {
        "filter": [{"integration": "alexa_devices", "domain": "notify"}]
    }


def test_sound_selector_offers_labeled_presets_and_custom_values() -> None:
    metadata = yaml.safe_load((INTEGRATION / "services.yaml").read_text("utf-8"))
    content_choices = metadata["send"]["fields"]["content"]["selector"]["choose"][
        "choices"
    ]
    sound = content_choices["Sound"]["selector"]["select"]

    assert sound["mode"] == "dropdown"
    assert sound["custom_value"] is True
    assert tuple(option["value"] for option in sound["options"]) == tuple(COMMON_SOUNDS)
    assert all(option["label"] for option in sound["options"])


def test_prosody_selectors_offer_named_and_bounded_custom_values() -> None:
    metadata = yaml.safe_load((INTEGRATION / "services.yaml").read_text("utf-8"))
    content_choices = metadata["send"]["fields"]["content"]["selector"]["choose"][
        "choices"
    ]
    fields = content_choices["Message"]["selector"]["object"]["fields"]

    expected = {
        "rate": ("Named rate", "Enter %-age", 20, 200, "%"),
        "pitch": ("Named pitch", "Enter %-age", -33.3, 50, "%"),
        "volume": (
            "Named volume",
            "Enter dB adjustment",
            -6,
            6,
            "dB",
        ),
    }
    for field, (named, custom, minimum, maximum, unit) in expected.items():
        choices = fields[field]["selector"]["choose"]["choices"]
        assert tuple(choices) == (named, custom)
        assert choices[named]["selector"]["select"]["mode"] == "dropdown"
        number = choices[custom]["selector"]["number"]
        assert number == {
            "min": minimum,
            "max": maximum,
            "step": "any",
            "unit_of_measurement": unit,
            "mode": "box",
        }


def test_content_selector_makes_content_and_message_options_exclusive() -> None:
    metadata = yaml.safe_load((INTEGRATION / "services.yaml").read_text("utf-8"))
    content = metadata["send"]["fields"]["content"]
    choices = content["selector"]["choose"]["choices"]

    assert content["required"] is True
    assert tuple(choices) == ("Message", "Sound", "Raw SSML")
    assert tuple(next(iter(choice["selector"])) for choice in choices.values()) == (
        "object",
        "select",
        "text",
    )
    message_fields = choices["Message"]["selector"]["object"]["fields"]
    assert tuple(message_fields) == (
        "text",
        "voice",
        "rate",
        "pitch",
        "volume",
        "whisper",
        "emotion",
        "emotion_intensity",
        "domain",
    )
    assert message_fields["text"]["required"] is True
    assert choices["Raw SSML"]["selector"] == {"text": {"multiline": True}}

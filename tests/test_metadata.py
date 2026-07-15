"""Tests for integration metadata files."""

import json
from pathlib import Path

import yaml

from custom_components.alexa_announcement_builder.const import (
    COMMON_SOUND_NAMES,
    COMMON_SOUNDS,
    NAMED_VOICES,
)

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "alexa_announcement_builder"


def _sequence_fields(metadata: dict) -> tuple[dict, dict]:
    sequence = metadata["send"]["fields"]["sequence"]
    return sequence, sequence["selector"]["object"]["fields"]


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
        "sequence",
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
    _, fields = _sequence_fields(metadata)
    selector = fields["voice"]["selector"]["select"]

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
    _, fields = _sequence_fields(metadata)
    sound = fields["sound"]["selector"]["select"]

    assert sound["mode"] == "dropdown"
    assert sound["custom_value"] is True
    assert tuple(option["value"] for option in sound["options"]) == tuple(
        COMMON_SOUND_NAMES.values()
    )
    assert tuple(COMMON_SOUND_NAMES) == tuple(COMMON_SOUNDS)
    assert all(option["label"] for option in sound["options"])
    assert all(option["label"] == option["value"] for option in sound["options"])


def test_prosody_selectors_offer_named_and_bounded_custom_values() -> None:
    metadata = yaml.safe_load((INTEGRATION / "services.yaml").read_text("utf-8"))
    _, fields = _sequence_fields(metadata)

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


def test_sequence_selector_is_repeatable_and_not_nested() -> None:
    metadata = yaml.safe_load((INTEGRATION / "services.yaml").read_text("utf-8"))
    sequence, fields = _sequence_fields(metadata)
    object_selector = sequence["selector"]["object"]

    assert sequence["required"] is True
    assert object_selector["multiple"] is True
    assert object_selector["label_field"] == "content_type"
    assert object_selector["description_field"] == "sound"
    assert tuple(fields) == (
        "content_type",
        "text",
        "sound",
        "raw_ssml",
        "voice",
        "rate",
        "pitch",
        "volume",
        "whisper",
        "emotion",
        "emotion_intensity",
        "domain",
    )
    assert fields["content_type"]["required"] is True
    assert fields["content_type"]["selector"] == {
        "select": {"options": ["Message", "Sound", "Raw SSML"]}
    }
    assert fields["text"]["selector"] == {"text": {"multiline": True}}
    assert fields["raw_ssml"]["selector"] == {"text": {"multiline": True}}
    assert all("object" not in field["selector"] for field in fields.values())

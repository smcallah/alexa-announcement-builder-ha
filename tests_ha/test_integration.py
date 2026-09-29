"""Run the integration inside a real Home Assistant instance."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.alexa_announcement_builder import volume
from custom_components.alexa_announcement_builder.const import DOMAIN

_DOORBELL = "soundbank://soundlibrary/home/amzn_sfx_doorbell_chime_01"


@dataclass
class Echo:
    """Entity IDs registered for one Alexa Devices Echo."""

    announce: str
    speak: str
    media_player: str


def _add_echo(hass: HomeAssistant, name: str, volume_level: float) -> Echo:
    """Register an Echo the way Alexa Devices does, with its current volume."""
    alexa_entry = MockConfigEntry(domain="alexa_devices")
    alexa_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=alexa_entry.entry_id,
        identifiers={("alexa_devices", name)},
    )
    registry = er.async_get(hass)

    def register(domain: str, key: str | None) -> str:
        return registry.async_get_or_create(
            domain,
            "alexa_devices",
            f"{name}-{key}" if key else name,
            config_entry=alexa_entry,
            device_id=device.id,
            suggested_object_id=f"{name}_{key}" if key else name,
            translation_key=key,
        ).entity_id

    echo = Echo(
        announce=register("notify", "announce"),
        speak=register("notify", "speak"),
        media_player=register("media_player", None),
    )
    hass.states.async_set(echo.media_player, "idle", {"volume_level": volume_level})
    return echo


@pytest.fixture
async def notify_calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Set up the integration and capture the notify calls it makes."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    # Registered after setup so it replaces the real notify entity service.
    return async_mock_service(hass, "notify", "send_message")


@pytest.fixture
def volume_calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Handle media_player.volume_set by updating the player's state."""
    calls: list[ServiceCall] = []

    async def volume_set(call: ServiceCall) -> None:
        calls.append(call)
        state = hass.states.get(call.data["entity_id"])
        hass.states.async_set(
            call.data["entity_id"],
            state.state,
            {**state.attributes, "volume_level": call.data["volume_level"]},
        )

    hass.services.async_register("media_player", "volume_set", volume_set)
    return calls


async def test_config_flow_creates_single_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "send")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_send_builds_sequence_with_home_assistant_validators(
    hass: HomeAssistant, notify_calls: list[ServiceCall]
) -> None:
    echo = _add_echo(hass, "office", 0.4)

    await hass.services.async_call(
        DOMAIN,
        "send",
        {
            "target": [echo.speak],
            # Home Assistant's own boolean validator accepts YAML-style strings.
            "adjust_volume": "off",
            "sequence": [
                {"content_type": "Message", "text": "Door.", "voice": "Joanna"},
                {"content_type": "Sound", "sound": "Doorbell chime"},
            ],
        },
        blocking=True,
    )

    assert len(notify_calls) == 1
    assert notify_calls[0].data == {
        "entity_id": [echo.speak],
        "message": f'<voice name="Joanna">Door.</voice><audio src="{_DOORBELL}"/>',
    }


async def test_send_rejects_invalid_data(
    hass: HomeAssistant, notify_calls: list[ServiceCall]
) -> None:
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "send",
            {"target": "light.office", "text": "Hello."},
            blocking=True,
        )
    assert notify_calls == []


async def test_sound_rejected_for_renamed_announce_entity(
    hass: HomeAssistant, notify_calls: list[ServiceCall]
) -> None:
    echo = _add_echo(hass, "hallway", 0.4)
    er.async_get(hass).async_update_entity(
        echo.announce, new_entity_id="notify.hallway_echo"
    )

    with pytest.raises(ServiceValidationError, match="notify.hallway_echo"):
        await hass.services.async_call(
            DOMAIN,
            "send",
            {
                "target": "notify.hallway_echo",
                "sequence": [{"content_type": "Sound", "sound": "Doorbell chime"}],
            },
            blocking=True,
        )
    assert notify_calls == []


async def test_sound_allowed_for_speak_entity_renamed_like_announce(
    hass: HomeAssistant, notify_calls: list[ServiceCall]
) -> None:
    echo = _add_echo(hass, "kitchen", 0.4)
    er.async_get(hass).async_update_entity(
        echo.speak, new_entity_id="notify.kitchen_announce"
    )

    await hass.services.async_call(
        DOMAIN,
        "send",
        {
            "target": "notify.kitchen_announce",
            "sequence": [{"content_type": "Sound", "sound": "Doorbell chime"}],
        },
        blocking=True,
    )
    assert len(notify_calls) == 1


async def test_temporary_volume_restores_in_background(
    hass: HomeAssistant,
    notify_calls: list[ServiceCall],
    volume_calls: list[ServiceCall],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(volume, "VOLUME_SETTLE_SECONDS", 0)
    office = _add_echo(hass, "office", 0.25)
    kitchen = _add_echo(hass, "kitchen", 0.45)

    await hass.services.async_call(
        DOMAIN,
        "send",
        {
            "target": [office.announce, kitchen.announce],
            "text": "Dinner is ready.",
            "adjust_volume": True,
            "announcement_volume": 80,
            "restore_after": 1,
        },
        blocking=True,
    )

    # The action returns once the message is sent, before the restore.
    assert len(notify_calls) == 1
    assert hass.states.get(office.media_player).attributes["volume_level"] == 0.8
    assert hass.states.get(kitchen.media_player).attributes["volume_level"] == 0.8

    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(office.media_player).attributes["volume_level"] == 0.25
    assert hass.states.get(kitchen.media_player).attributes["volume_level"] == 0.45
    assert [call.data["volume_level"] for call in volume_calls] == [
        0.8,
        0.8,
        0.45,
        0.25,
    ]

"""Tests for the Alexa Announcement Builder service."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call, patch

import pytest
import voluptuous as vol
from homeassistant.exceptions import ServiceValidationError

from custom_components.alexa_announcement_builder import (
    SEND_SCHEMA,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)

_SLEEP = "custom_components.alexa_announcement_builder.volume.asyncio.sleep"


class _States:
    """Small mutable Home Assistant state-machine stand-in."""

    def __init__(self, volumes: dict[str, float]) -> None:
        self.volumes = volumes

    def get(self, entity_id: str) -> SimpleNamespace | None:
        volume = self.volumes.get(entity_id)
        if volume is None:
            return None
        return SimpleNamespace(attributes={"volume_level": volume})


def _hass(
    *,
    entries: dict[str, SimpleNamespace] | None = None,
    entries_by_device: dict[str, list[SimpleNamespace]] | None = None,
    states: _States | None = None,
    async_call: AsyncMock | None = None,
) -> SimpleNamespace:
    """Build a Home Assistant stand-in with an entity registry."""
    entries = entries or {}
    background_tasks: list[asyncio.Task] = []

    def create_background_task(target, name: str) -> asyncio.Task:
        task = asyncio.create_task(target, name=name)
        background_tasks.append(task)
        return task

    return SimpleNamespace(
        data={},
        entity_registry=SimpleNamespace(
            async_get=Mock(side_effect=entries.get),
            entries_by_device=entries_by_device or {},
        ),
        services=SimpleNamespace(
            async_register=Mock(), async_call=async_call or AsyncMock()
        ),
        states=states or _States({}),
        background_tasks=background_tasks,
        async_create_background_task=create_background_task,
    )


def _notify_entry(translation_key: str, device_id: str | None = None):
    """Build an Alexa Devices notify-entity registry entry."""
    return SimpleNamespace(
        device_id=device_id,
        platform="alexa_devices",
        translation_key=translation_key,
    )


def _volume_hass(
    volumes: dict[str, float],
) -> tuple[SimpleNamespace, Mock, AsyncMock]:
    """Build a service environment with paired Alexa notify/media entities."""
    states = _States(volumes)
    entries: dict[str, SimpleNamespace] = {}
    entries_by_device: dict[str, list[SimpleNamespace]] = {}

    for media_player in volumes:
        suffix = media_player.removeprefix("media_player.")
        device_id = f"device-{suffix}"
        entries[f"notify.{suffix}_announce"] = _notify_entry("announce", device_id)
        entries_by_device[device_id] = [
            SimpleNamespace(
                entity_id=media_player,
                domain="media_player",
                platform="alexa_devices",
            )
        ]

    async def async_call(
        domain: str,
        service: str,
        service_data: dict,
        *,
        target: dict,
        blocking: bool,
    ) -> None:
        if (domain, service) == ("media_player", "volume_set"):
            states.volumes[target["entity_id"]] = service_data["volume_level"]

    service_call = AsyncMock(side_effect=async_call)
    hass = _hass(
        entries=entries,
        entries_by_device=entries_by_device,
        states=states,
        async_call=service_call,
    )
    return hass, hass.services.async_register, service_call


async def _handler(hass: SimpleNamespace):
    """Register the service and return its handler."""
    assert await async_setup(hass, {}) is True
    return hass.services.async_register.call_args.args[2]


def _volume_calls(service_call: AsyncMock) -> list[float]:
    """Return the volume levels set, in call order."""
    return [
        args.args[2]["volume_level"]
        for args in service_call.await_args_list
        if args.args[:2] == ("media_player", "volume_set")
    ]


async def test_config_entry_setup_and_unload() -> None:
    """A config entry needs no additional runtime resources."""
    hass = SimpleNamespace()
    entry = SimpleNamespace()

    assert await async_setup_entry(hass, entry) is True
    assert await async_unload_entry(hass, entry) is True


async def test_service_forwards_to_notify_send_message() -> None:
    hass = _hass()
    handler = await _handler(hass)
    services = hass.services

    services.async_register.assert_called_once()
    domain, service, _ = services.async_register.call_args.args
    assert (domain, service) == ("alexa_announcement_builder", "send")
    assert services.async_register.call_args.kwargs["schema"] is SEND_SCHEMA

    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_speak",
            "content": {
                "active_choice": "Message",
                "Message": {
                    "text": "This is a test.",
                    "voice": "original_alexa",
                    "rate": {
                        "active_choice": "Named rate",
                        "Named rate": "x-slow",
                    },
                },
            },
        }
    )
    await handler(SimpleNamespace(data=data))

    services.async_call.assert_awaited_once_with(
        "notify",
        "send_message",
        {
            "message": '<voice name="Kendra"> </voice>'
            '<prosody rate="x-slow">This is a test.</prosody>'
        },
        target={"entity_id": "notify.office_echo_speak"},
        blocking=True,
    )


async def test_service_forwards_selected_sound_to_notify() -> None:
    hass = _hass()
    handler = await _handler(hass)

    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_speak",
            "content": {
                "active_choice": "Sound",
                "Sound": "positive_response",
            },
        }
    )
    await handler(SimpleNamespace(data=data))

    hass.services.async_call.assert_awaited_once_with(
        "notify",
        "send_message",
        {
            "message": '<audio src="soundbank://soundlibrary/ui/gameshow/'
            'amzn_ui_sfx_gameshow_positive_response_01"/>'
        },
        target={"entity_id": "notify.office_echo_speak"},
        blocking=True,
    )


async def test_service_forwards_ordered_sequence_to_notify() -> None:
    hass = _hass()
    handler = await _handler(hass)

    data = SEND_SCHEMA(
        {
            "target": [
                "notify.office_echo_speak",
                "notify.kitchen_echo_speak",
            ],
            "sequence": [
                {
                    "content": {
                        "active_choice": "Message",
                        "Message": {"text": "Someone is at the door."},
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
                            "text": "Please check the camera.",
                            "voice": "Joanna",
                        },
                    }
                },
            ],
        }
    )
    await handler(SimpleNamespace(data=data))

    hass.services.async_call.assert_awaited_once_with(
        "notify",
        "send_message",
        {
            "message": "Someone is at the door."
            '<audio src="soundbank://soundlibrary/doors/doors_knocks/knocks_01"/>'
            '<voice name="Joanna">Please check the camera.</voice>'
        },
        target={
            "entity_id": [
                "notify.office_echo_speak",
                "notify.kitchen_echo_speak",
            ]
        },
        blocking=True,
    )


async def test_forwarding_error_propagates() -> None:
    hass = _hass(async_call=AsyncMock(side_effect=RuntimeError("failed")))
    handler = await _handler(hass)

    data = SEND_SCHEMA({"target": "notify.office_echo_speak", "text": "Hello."})

    with pytest.raises(RuntimeError, match="failed"):
        await handler(SimpleNamespace(data=data))


_SOUND_CONTENT = {"content": {"active_choice": "Sound", "Sound": "doorbell_chime"}}
_SOUND_SEQUENCE = {
    "sequence": [
        {"content": {"active_choice": "Message", "Message": {"text": "Listen."}}},
        _SOUND_CONTENT,
    ]
}


@pytest.mark.parametrize(
    ("target", "content"),
    [
        ("notify.office_echo_announce", _SOUND_CONTENT),
        ("notify.office_echo_announce_2", _SOUND_CONTENT),
        (["notify.office_echo_speak", "notify.office_echo_announce"], _SOUND_CONTENT),
        (["notify.office_echo_speak", "notify.office_echo_announce"], _SOUND_SEQUENCE),
    ],
)
async def test_sound_rejected_for_unregistered_announce_entity_ids(
    target: str | list[str], content: dict
) -> None:
    """Entities outside Alexa Devices fall back to the entity ID pattern."""
    hass = _hass()
    handler = await _handler(hass)
    data = SEND_SCHEMA({"target": target, **content})

    with pytest.raises(ServiceValidationError, match="notify.office_echo_announce"):
        await handler(SimpleNamespace(data=data))

    hass.services.async_call.assert_not_awaited()


async def test_sound_rejected_for_renamed_alexa_announce_entity() -> None:
    hass = _hass(entries={"notify.hallway": _notify_entry("announce")})
    handler = await _handler(hass)
    data = SEND_SCHEMA({"target": "notify.hallway", **_SOUND_SEQUENCE})

    with pytest.raises(ServiceValidationError, match="Speak targets"):
        await handler(SimpleNamespace(data=data))

    hass.services.async_call.assert_not_awaited()


async def test_sound_allowed_for_speak_entity_with_announce_like_id() -> None:
    hass = _hass(entries={"notify.office_announce": _notify_entry("speak")})
    handler = await _handler(hass)
    data = SEND_SCHEMA({"target": "notify.office_announce", **_SOUND_CONTENT})

    await handler(SimpleNamespace(data=data))

    hass.services.async_call.assert_awaited_once()


async def test_message_allowed_for_announce_entity() -> None:
    hass = _hass(entries={"notify.hallway": _notify_entry("announce")})
    handler = await _handler(hass)
    data = SEND_SCHEMA({"target": "notify.hallway", "text": "Hello."})

    await handler(SimpleNamespace(data=data))

    hass.services.async_call.assert_awaited_once()


async def test_temporary_volume_restores_each_device_to_its_original_level() -> None:
    hass, _, service_call = _volume_hass(
        {
            "media_player.kitchen_echo": 0.25,
            "media_player.office_echo": 0.45,
        }
    )
    handler = await _handler(hass)
    data = SEND_SCHEMA(
        {
            "target": [
                "notify.office_echo_announce",
                "notify.kitchen_echo_announce",
            ],
            "text": "Dinner is ready.",
            "adjust_volume": True,
        }
    )

    with patch(_SLEEP, new=AsyncMock()) as sleep:
        await handler(SimpleNamespace(data=data))
        await asyncio.gather(*hass.background_tasks)

    assert service_call.await_args_list == [
        call(
            "media_player",
            "volume_set",
            {"volume_level": 0.7},
            target={"entity_id": "media_player.kitchen_echo"},
            blocking=True,
        ),
        call(
            "media_player",
            "volume_set",
            {"volume_level": 0.7},
            target={"entity_id": "media_player.office_echo"},
            blocking=True,
        ),
        call(
            "notify",
            "send_message",
            {"message": "Dinner is ready."},
            target={
                "entity_id": [
                    "notify.office_echo_announce",
                    "notify.kitchen_echo_announce",
                ]
            },
            blocking=True,
        ),
        call(
            "media_player",
            "volume_set",
            {"volume_level": 0.25},
            target={"entity_id": "media_player.kitchen_echo"},
            blocking=True,
        ),
        call(
            "media_player",
            "volume_set",
            {"volume_level": 0.45},
            target={"entity_id": "media_player.office_echo"},
            blocking=True,
        ),
    ]
    assert sleep.await_args_list == [call(1), call(10)]
    assert hass.states.volumes == {
        "media_player.kitchen_echo": 0.25,
        "media_player.office_echo": 0.45,
    }


async def test_temporary_volume_returns_before_restore_delay() -> None:
    hass, _, service_call = _volume_hass({"media_player.office_echo": 0.3})
    handler = await _handler(hass)
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_announce",
            "text": "Test.",
            "adjust_volume": True,
        }
    )
    release_restore = asyncio.Event()

    async def controlled_sleep(delay: int) -> None:
        if delay == 10:
            await release_restore.wait()

    with patch(_SLEEP, side_effect=controlled_sleep):
        await handler(SimpleNamespace(data=data))

        assert service_call.await_args_list[-1].args[:2] == (
            "notify",
            "send_message",
        )
        assert hass.states.volumes["media_player.office_echo"] == 0.7
        (restore,) = hass.background_tasks
        assert not restore.done()

        release_restore.set()
        await restore

    assert hass.states.volumes["media_player.office_echo"] == 0.3


async def test_temporary_volume_restores_immediately_when_notify_fails() -> None:
    hass, _, service_call = _volume_hass({"media_player.office_echo": 0.3})

    original_side_effect = service_call.side_effect

    async def fail_notify(*args, **kwargs) -> None:
        if args[:2] == ("notify", "send_message"):
            raise RuntimeError("send failed")
        await original_side_effect(*args, **kwargs)

    service_call.side_effect = fail_notify
    handler = await _handler(hass)
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_announce",
            "text": "Test.",
            "adjust_volume": True,
            "announcement_volume": 80,
            "restore_after": 20,
        }
    )

    with (
        patch(_SLEEP, new=AsyncMock()) as sleep,
        pytest.raises(RuntimeError, match="send failed"),
    ):
        await handler(SimpleNamespace(data=data))

    assert sleep.await_args_list == [call(1)]
    assert hass.background_tasks == []
    assert hass.states.volumes["media_player.office_echo"] == 0.3
    assert service_call.await_args_list[-1] == call(
        "media_player",
        "volume_set",
        {"volume_level": 0.3},
        target={"entity_id": "media_player.office_echo"},
        blocking=True,
    )


async def test_manual_volume_change_is_not_overwritten_by_restore() -> None:
    hass, _, service_call = _volume_hass({"media_player.office_echo": 0.3})
    original_side_effect = service_call.side_effect

    async def change_volume_during_notify(*args, **kwargs) -> None:
        await original_side_effect(*args, **kwargs)
        if args[:2] == ("notify", "send_message"):
            hass.states.volumes["media_player.office_echo"] = 0.55

    service_call.side_effect = change_volume_during_notify
    handler = await _handler(hass)
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_announce",
            "text": "Test.",
            "adjust_volume": True,
        }
    )

    with patch(_SLEEP, new=AsyncMock()):
        await handler(SimpleNamespace(data=data))
        await asyncio.gather(*hass.background_tasks)

    assert hass.states.volumes["media_player.office_echo"] == 0.55
    assert service_call.await_count == 2


async def test_overlapping_send_keeps_original_volume_and_takes_over_restore() -> None:
    hass, _, service_call = _volume_hass({"media_player.office_echo": 0.3})
    handler = await _handler(hass)
    first = SEND_SCHEMA(
        {
            "target": "notify.office_echo_announce",
            "text": "First.",
            "adjust_volume": True,
        }
    )
    second = SEND_SCHEMA(
        {
            "target": "notify.office_echo_announce",
            "text": "Second.",
            "adjust_volume": True,
            "announcement_volume": 90,
        }
    )
    release_restores = asyncio.Event()

    async def controlled_sleep(delay: int) -> None:
        if delay == 10:
            await release_restores.wait()

    with patch(_SLEEP, side_effect=controlled_sleep):
        await handler(SimpleNamespace(data=first))
        # The second send does not wait for the first send's restore delay.
        await asyncio.wait_for(handler(SimpleNamespace(data=second)), timeout=1)

        assert hass.states.volumes["media_player.office_echo"] == 0.9
        release_restores.set()
        await asyncio.gather(*hass.background_tasks)

    # Only the second send restores, and it restores the pre-first-send volume.
    assert _volume_calls(service_call) == [0.7, 0.9, 0.3]
    assert hass.states.volumes["media_player.office_echo"] == 0.3


async def test_cancelled_restore_delay_still_restores_volume() -> None:
    """Home Assistant cancels background tasks when it shuts down."""
    hass, _, _ = _volume_hass({"media_player.office_echo": 0.3})
    handler = await _handler(hass)
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_announce",
            "text": "Test.",
            "adjust_volume": True,
        }
    )

    restore_waiting = asyncio.Event()

    async def controlled_sleep(delay: int) -> None:
        if delay == 10:
            restore_waiting.set()
            await asyncio.Event().wait()

    with patch(_SLEEP, side_effect=controlled_sleep):
        await handler(SimpleNamespace(data=data))
        (restore,) = hass.background_tasks
        await restore_waiting.wait()
        restore.cancel()
        with pytest.raises(asyncio.CancelledError):
            await restore

    assert hass.states.volumes["media_player.office_echo"] == 0.3


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("announcement_volume", 0),
        ("announcement_volume", 101),
        ("restore_after", -1),
        ("restore_after", 301),
    ],
)
def test_temporary_volume_schema_rejects_out_of_range_values(
    field: str, value: int
) -> None:
    with pytest.raises(vol.Invalid):
        SEND_SCHEMA(
            {
                "target": "notify.office_echo_announce",
                "text": "Test.",
                "adjust_volume": True,
                field: value,
            }
        )

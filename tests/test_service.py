"""Tests for the Alexa Announcement Builder service."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call, patch

import pytest
import voluptuous as vol

from custom_components.alexa_announcement_builder import (
    SEND_SCHEMA,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)


class _States:
    """Small mutable Home Assistant state-machine stand-in."""

    def __init__(self, volumes: dict[str, float]) -> None:
        self.volumes = volumes

    def get(self, entity_id: str) -> SimpleNamespace | None:
        volume = self.volumes.get(entity_id)
        if volume is None:
            return None
        return SimpleNamespace(attributes={"volume_level": volume})


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
        notify = f"notify.{suffix}_announce"
        entries[notify] = SimpleNamespace(device_id=device_id)
        entries_by_device[device_id] = [
            SimpleNamespace(
                entity_id=media_player,
                domain="media_player",
                platform="alexa_devices",
            )
        ]

    registry = SimpleNamespace(
        async_get=Mock(side_effect=entries.get),
        entries_by_device=entries_by_device,
    )

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
    register = Mock()
    hass = SimpleNamespace(
        data={},
        entity_registry=registry,
        services=SimpleNamespace(async_register=register, async_call=service_call),
        states=states,
    )
    return hass, register, service_call


async def test_config_entry_setup_and_unload() -> None:
    """A config entry needs no additional runtime resources."""
    hass = SimpleNamespace()
    entry = SimpleNamespace()

    assert await async_setup_entry(hass, entry) is True
    assert await async_unload_entry(hass, entry) is True


async def test_service_forwards_to_notify_send_message() -> None:
    services = SimpleNamespace(async_register=Mock(), async_call=AsyncMock())
    hass = SimpleNamespace(services=services)

    assert await async_setup(hass, {}) is True

    services.async_register.assert_called_once()
    domain, service, handler = services.async_register.call_args.args
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
    services = SimpleNamespace(async_register=Mock(), async_call=AsyncMock())
    hass = SimpleNamespace(services=services)
    await async_setup(hass, {})
    handler = services.async_register.call_args.args[2]

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

    services.async_call.assert_awaited_once_with(
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
    services = SimpleNamespace(async_register=Mock(), async_call=AsyncMock())
    hass = SimpleNamespace(services=services)
    await async_setup(hass, {})
    handler = services.async_register.call_args.args[2]

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

    services.async_call.assert_awaited_once_with(
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
    services = SimpleNamespace(
        async_register=Mock(), async_call=AsyncMock(side_effect=RuntimeError("failed"))
    )
    hass = SimpleNamespace(services=services)
    await async_setup(hass, {})
    handler = services.async_register.call_args.args[2]

    data = SEND_SCHEMA({"target": "notify.office_echo_speak", "text": "Hello."})

    try:
        await handler(SimpleNamespace(data=data))
    except RuntimeError as err:
        assert str(err) == "failed"
    else:
        raise AssertionError("notify error did not propagate")


async def test_temporary_volume_restores_each_device_to_its_original_level() -> None:
    hass, register, service_call = _volume_hass(
        {
            "media_player.kitchen_echo": 0.25,
            "media_player.office_echo": 0.45,
        }
    )
    await async_setup(hass, {})
    handler = register.call_args.args[2]
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

    with patch(
        "custom_components.alexa_announcement_builder.volume.asyncio.sleep",
        new=AsyncMock(),
    ) as sleep:
        await handler(SimpleNamespace(data=data))

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


async def test_temporary_volume_restores_immediately_when_notify_fails() -> None:
    hass, register, service_call = _volume_hass({"media_player.office_echo": 0.3})

    original_side_effect = service_call.side_effect

    async def fail_notify(*args, **kwargs) -> None:
        if args[:2] == ("notify", "send_message"):
            raise RuntimeError("send failed")
        await original_side_effect(*args, **kwargs)

    service_call.side_effect = fail_notify
    await async_setup(hass, {})
    handler = register.call_args.args[2]
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
        patch(
            "custom_components.alexa_announcement_builder.volume.asyncio.sleep",
            new=AsyncMock(),
        ) as sleep,
        pytest.raises(RuntimeError, match="send failed"),
    ):
        await handler(SimpleNamespace(data=data))

    assert sleep.await_args_list == [call(1)]
    assert hass.states.volumes["media_player.office_echo"] == 0.3
    assert service_call.await_args_list[-1] == call(
        "media_player",
        "volume_set",
        {"volume_level": 0.3},
        target={"entity_id": "media_player.office_echo"},
        blocking=True,
    )


async def test_manual_volume_change_is_not_overwritten_by_restore() -> None:
    hass, register, service_call = _volume_hass({"media_player.office_echo": 0.3})
    original_side_effect = service_call.side_effect

    async def change_volume_during_notify(*args, **kwargs) -> None:
        await original_side_effect(*args, **kwargs)
        if args[:2] == ("notify", "send_message"):
            hass.states.volumes["media_player.office_echo"] = 0.55

    service_call.side_effect = change_volume_during_notify
    await async_setup(hass, {})
    handler = register.call_args.args[2]
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_announce",
            "text": "Test.",
            "adjust_volume": True,
        }
    )

    with patch(
        "custom_components.alexa_announcement_builder.volume.asyncio.sleep",
        new=AsyncMock(),
    ):
        await handler(SimpleNamespace(data=data))

    assert hass.states.volumes["media_player.office_echo"] == 0.55
    assert service_call.await_count == 2


async def test_overlapping_sends_capture_volume_after_device_lock() -> None:
    hass, register, service_call = _volume_hass({"media_player.office_echo": 0.3})
    await async_setup(hass, {})
    handler = register.call_args.args[2]
    data = SEND_SCHEMA(
        {
            "target": "notify.office_echo_announce",
            "text": "Test.",
            "adjust_volume": True,
        }
    )
    first_restore_waiting = asyncio.Event()
    release_first_restore = asyncio.Event()
    restore_delays = 0

    async def controlled_sleep(delay: int) -> None:
        nonlocal restore_delays
        if delay == 10:
            restore_delays += 1
            if restore_delays == 1:
                first_restore_waiting.set()
                await release_first_restore.wait()

    with patch(
        "custom_components.alexa_announcement_builder.volume.asyncio.sleep",
        side_effect=controlled_sleep,
    ):
        first = asyncio.create_task(handler(SimpleNamespace(data=data)))
        await first_restore_waiting.wait()

        second = asyncio.create_task(handler(SimpleNamespace(data=data)))
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.shield(second), timeout=0.01)

        assert service_call.await_count == 2
        release_first_restore.set()
        await first
        await second

    assert hass.states.volumes["media_player.office_echo"] == 0.3
    assert [
        args.args[2]["volume_level"]
        for args in service_call.await_args_list
        if args.args[:2] == ("media_player", "volume_set")
    ] == [0.7, 0.3, 0.7, 0.3]


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

"""Tests for the Alexa Announcement Builder service."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from custom_components.alexa_announcement_builder import (
    SEND_SCHEMA,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)


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
            "target": "notify.office_echo_speak",
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
        target={"entity_id": "notify.office_echo_speak"},
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

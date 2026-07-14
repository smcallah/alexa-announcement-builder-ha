"""Tests for the Alexa Announcement Builder config flow."""

from types import SimpleNamespace

from custom_components.alexa_announcement_builder.config_flow import (
    AlexaAnnouncementBuilderConfigFlow,
)


async def test_user_flow_shows_confirmation_form() -> None:
    flow = AlexaAnnouncementBuilderConfigFlow()

    result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["data_schema"]({}) == {}


async def test_user_flow_creates_entry() -> None:
    flow = AlexaAnnouncementBuilderConfigFlow()

    result = await flow.async_step_user({})

    assert result == {
        "type": "create_entry",
        "title": "Alexa Announcement Builder",
        "data": {},
    }


async def test_user_flow_allows_only_one_entry() -> None:
    flow = AlexaAnnouncementBuilderConfigFlow()
    flow.current_entries = [SimpleNamespace()]

    result = await flow.async_step_user()

    assert result == {"type": "abort", "reason": "single_instance_allowed"}

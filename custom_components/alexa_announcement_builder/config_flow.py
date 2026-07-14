"""Config flow for Alexa Announcement Builder."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN


class AlexaAnnouncementBuilderConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Alexa Announcement Builder config flow."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle setup initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title="Alexa Announcement Builder",
                data={},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )

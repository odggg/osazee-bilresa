"""UI setup for OSAZEE BILRESA. Author: OSAZEE."""
from homeassistant import config_entries
import voluptuous as vol
from . import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create exactly one local bridge."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="OSAZEE BILRESA", data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

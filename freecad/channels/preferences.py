# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

from __future__ import annotations

from .vendor.fcapi.preferences import (
    Preference,
    Preferences,
    auto_gui,
    validators as valid,
)
from .vendor.fcapi.lang import dtr


@auto_gui(
    default_ui_group="Channels",
    default_ui_page=dtr("Channels", "General"),
)
class ChannelsPreferences(Preferences):
    """
    Channels Import Preferences.
    """

    group = "Preferences/Mod/Channels/General"

    start_on_boot = Preference(
        group,
        name="start_on_boot",
        default=False,
        label=dtr("Channels", "Start Channels service on startup"),
        description=dtr(
            "Channels",
            "Start Channels service on startup and allow incoming connections.",
        ),
        ui_section=dtr("Channels", "Service"),
    )

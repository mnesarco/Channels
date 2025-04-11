# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

"""
FreeCAD Channels: Start Channels Main Service.
"""

from __future__ import annotations

from freecad.channels.config import commands, resources
from freecad.channels.vendor.fcapi.lang import QT_TRANSLATE_NOOP


@commands.add(
    label=QT_TRANSLATE_NOOP("Channels", "Start Channels Service"),
    tooltip=QT_TRANSLATE_NOOP("Channels", "Start Channels Service"),
    icon=resources.icon("start.svg"),
)
class StartService:
    """Start Channels Main Service."""

    def on_activated(self) -> None:
        from freecad.channels.service import service

        service.start()

    def is_active(self) -> bool:
        from freecad.channels.service import service

        return not service.is_running()


@commands.add(
    label=QT_TRANSLATE_NOOP("Channels", "Stop Channels Service"),
    tooltip=QT_TRANSLATE_NOOP("Channels", "Stop Channels Service"),
    icon=resources.icon("stop.svg"),
)
class StopService:
    """Stop Channels Main Service."""

    def on_activated(self) -> None:
        from freecad.channels.service import service

        service.stop()

    def is_active(self) -> bool:
        from freecad.channels.service import service

        return service.is_running()

# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

from freecad.channels.api import ServiceRequest, channel_handler
from .config import preferences

start_on_boot = preferences.start_on_boot()

@channel_handler(name="FreeCAD", queue_size=50, start=start_on_boot)
def service(data: ServiceRequest) -> None:
    pass

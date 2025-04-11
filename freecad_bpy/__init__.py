# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

"""
FreeCAD Channels for Blender.
"""

from .service import service


def register() -> None:
    service.start()


def unregister() -> None:
    service.stop()

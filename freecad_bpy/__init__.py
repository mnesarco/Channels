# SPDX-License: GPL-3.0
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

"""
FreeCAD Channels for Blender.
"""

from .service import service


def register() -> None:
    service.start()


def unregister() -> None:
    service.stop()

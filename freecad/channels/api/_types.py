# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

"""
FreeCAD Channels: Common types.
"""

from typing import Protocol


class ServiceController(Protocol):
    def stop(self) -> None: ...
    def start(self) -> None: ...
    def is_running(self) -> bool: ...

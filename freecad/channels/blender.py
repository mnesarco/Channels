# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

from __future__ import annotations

from typing import TYPE_CHECKING

from freecad.channels.api import ServiceClient, ServiceRequest, find_channel_service

import FreeCAD as App  # type: ignore

if TYPE_CHECKING:
    from pathlib import Path


class _State:
    client: ServiceClient | None = None


def find_blender(*, rediscover: bool = False, timeout: float = 5) -> ServiceClient:
    if rediscover or _State.client is None:
        servers = find_channel_service(filter=["Blender"], timeout=timeout, maxcount=1)
        if servers:
            App.Console.PrintMessage(f"Blender channel found: {servers[0]}\n")
            _State.client = ServiceClient(servers[0])
        else:
            msg = "Blender channel server not found"
            raise RuntimeError(msg)
    return _State.client


def send_objects(path: Path, timeout: float = 5) -> None:
    client = find_blender()
    client.send(
        ServiceRequest(
            "FreeCAD",
            data={
                "action": "import_file",
                "path": str(path),
            },
        ),
        timeout=timeout,
    )

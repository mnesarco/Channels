# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

from __future__ import annotations

import bpy

from .freecad.channels.api import (
    Channel,
    Service,
    ServiceController,
    ServiceRequestHandler,
    ServiceRegistry,
    ServiceRequest,  # noqa: F401
)


class channel_handler(Channel):  # noqa: N801
    """
    Channel decorator to implement services in Blender.
    """

    registry = ServiceRegistry()  # Default registry

    class Controller(ServiceController):
        """
        Service Controller for Blender.

        This class is the Glue between FreeCAD Channels service and
        Blender internal threading/state system.
        """

        def __init__(
            self,
            service: Service,
            handler: ServiceRequestHandler,
            poll: float = 0.5,
        ) -> None:
            """
            Initialize the BpyServiceCtrl.

            This constructor should not be called directly. It is managed.

            :param service: The service instance to control in Blender.
            :param handler: A function to handle service requests.
            :param poll: The polling interval in seconds.
            """

            def timeout() -> float:
                if not service.is_running():
                    service.start()
                for data in service:
                    handler(data)
                return poll

            self.timeout = timeout
            self.service = service

        def stop(self) -> None:
            if bpy.app.timers.is_registered(self.timeout):
                bpy.app.timers.unregister(self.timeout)
            if self.service.is_running():
                self.service.shutdown()

        def start(self) -> None:
            if not bpy.app.timers.is_registered(self.timeout):
                bpy.app.timers.register(self.timeout, persistent=True)

        def is_running(self) -> bool:
            return self.service.is_running()

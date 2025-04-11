# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

"""
FreeCAD Channels: Qt Service dispatcher.
"""

from __future__ import annotations

from ._service import Channel, Service, ServiceRegistry, ServiceRequestHandler
from ._types import ServiceController


class channel_handler(Channel):  # noqa: N801
    """
    Channel decorator to implement services in Qt.
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
            Initialize the Controller.

            This constructor should not be called directly. It is managed.

            :param service: The service instance to control in Blender.
            :param handler: A function to handle service requests.
            :param poll: The polling interval in seconds.
            """
            try:
                from PySide6.QtCore import QTimer  # type: ignore
            except ImportError:
                try:
                    from PySide2.QtCore import QTimer  # type: ignore
                except ImportError:
                    from PySide.QtCore import QTimer  # type: ignore

            def timeout() -> None:
                if not service.is_running():
                    service.start()
                for data in service:
                    handler(data)

            timer = QTimer()
            timer.setInterval(int(poll * 1000))
            timer.timeout.connect(timeout)
            self.timer = timer
            self.service = service

        def stop(self) -> None:
            if self.timer.isActive():
                self.timer.stop()
            self.service.shutdown()

        def start(self) -> None:
            if not self.timer.isActive():
                self.timer.start()

        def is_running(self) -> bool:
            return self.timer.isActive()

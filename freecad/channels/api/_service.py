# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

# ruff: noqa: S310

"""
FreeCAD Channels: Services.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from itertools import count
from logging import getLogger
from queue import Empty, Queue
from threading import Thread
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, TypeAlias
from urllib import request as _request, error

if TYPE_CHECKING:
    from collections.abc import Iterator

    from ._types import ServiceController


@dataclass(unsafe_hash=True, slots=True, frozen=True)
class ServiceAddress:
    """
    Address information for a service.
    """

    host: str
    name: str
    port: int

    def __str__(self) -> str:
        return f"{DISCOVERY_SERVICE_TYPE}:{self.name}@{self.host}:{self.port}"

    @property
    def display(self) -> str:
        return f"{self.name}@{self.host}:{self.port}"

    @classmethod
    def parse(cls, address: str) -> ServiceAddress:
        parts = address.split(":")
        if parts[0] != DISCOVERY_SERVICE_TYPE:
            msg = f"Invalid service address: {address}"
            raise ValueError(msg)
        name, host = parts[1].split("@")
        return cls(host, name, int(parts[2]))


@dataclass(kw_only=True)
class ServiceRegistry:
    """Service registry to announce and find services."""

    interval: float = 1.0

    _actions: Queue[tuple[str, ServiceAddress | None]] = field(init=False, default_factory=Queue)
    _services: dict[str, ServiceAddress] = field(init=False, default_factory=dict)
    _shutdown: bool = field(init=False, default=False)
    _announce_thread: Thread | None = field(init=False, default=None)

    def register(self, service: ServiceAddress) -> None:
        """
        Register a service to announce.

        The service is registered in the local service registry and
        announced on the network using pseudo mDNS.

        :param service: The service to register.
        """
        self._actions.put(("register", service))
        if self._announce_thread is None:
            self._start_announce()

    def unregister(self, service: ServiceAddress) -> None:
        """
        Unregister a service.

        The service is removed from the local service registry and
        will not be announced on the network anymore.

        :param service: The service to unregister.
        """
        self._actions.put(("unregister", service))

    def shutdown(self) -> None:
        """
        Shutdown the service registry and stop announcing and discovering services.
        """
        self._actions.put(("shutdown", None))

    def _update(self) -> None:
        with suppress(Empty):
            while True:
                action, service = self._actions.get(block=False)
                match action:
                    case "shutdown":
                        logger.info("Shutting down discovery service")
                        self._shutdown = True
                        return
                    case "register":
                        logger.info("Registering service %s", service.name)
                        self._services[service.name] = service
                    case "unregister" if service.name in self._services:
                        logger.info("Unregistering service %s", service.name)
                        del self._services[service.name]
                self._actions.task_done()

    def _run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            while not self._shutdown:
                self._announce(sock)
                time.sleep(self.interval)
                self._update()
        except Exception as ex:
            logger.exception(str(ex.args))
        finally:
            with suppress(Exception):
                self._announce_thread = None
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
        logger.info("Discovery service stopped")

    def _announce(self, sock: socket.socket) -> None:
        for service in self._services.values():
            sock.sendto(str(service).encode("utf-8"), DISCOVERY_SERVICE_ADDR)

    def _start_announce(self) -> None:
        logger.info("Starting announcement service")
        self._announce_thread = threading.Thread(
            target=self._run,
            name=f"freecad-channels-registry-{next(TID)}",
        )
        self._announce_thread.daemon = True
        self._announce_thread.start()
        logger.info("Announcement service started")

    def create_service(
        self,
        name: str,
        queue: Queue[dict] | None = None,
        *,
        start: bool = True,
    ) -> Service:
        return Service(self, name, queue or Queue(), start=start)


@dataclass(slots=True)
class ServiceRequest:
    name: str
    reply_to: int | None = None
    data: dict[str, Any] = field(default_factory=dict)


class Service:
    """FreeCAD Channels Service"""

    def __init__(
        self,
        registry: ServiceRegistry,
        name: str,
        request_queue: Queue[ServiceRequest],
        *,
        start: bool = True,
    ) -> None:
        """
        Initialize the service.

        :param registry: The service registry to register the service in.
        :param name: The name of the service.
        :param request_queue: The queue to receive requests from.
        """
        self.registry = registry
        self.name = name
        self.port = None
        self.host = None
        self._server = None
        self._thread = None
        self._queue = request_queue or Queue()
        if start:
            self.start()

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run,
            name=f"freecad-channels-{self.name}-{next(TID)}",
            daemon=True,
        )
        self._thread.start()

    def is_full(self) -> bool:
        return self._queue.maxsize > 0 and self._queue.qsize() >= self._queue.maxsize

    def _run(self) -> None:
        self._server = HTTPServer((LOCALHOST, 0), self._handler())
        self.host, self.port = self._server.server_address
        self.registry.register(self.address())
        self._server.serve_forever()
        self.registry.unregister(self.address())

    def address(self) -> ServiceAddress:
        return ServiceAddress(self.host, self.name, self.port)

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        service = self

        class ServiceHandler(BaseHTTPRequestHandler):
            """Http Handler for the service."""

            def do_GET(self) -> None:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({
                        "status": "full" if service.is_full() else "ok",
                        "service": str(service.address()),
                    }).encode("utf-8"),
                )

            def do_POST(self) -> None:
                queue = service._queue  # noqa: SLF001
                if service.is_full():
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(
                        json.dumps({
                            "status": "rejected",
                            "message": "queue full",
                        }).encode("utf-8"),
                    )
                    return

                content_length = int(self.headers.get("Content-Length"))
                body = self.rfile.read(content_length).decode("utf-8")
                data = json.loads(body)
                queue.put(
                    ServiceRequest(
                        data.get("name"),
                        data.get("reply_to"),
                        data.get("data"),
                    ),
                )
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))

        return ServiceHandler

    def __iter__(self) -> Iterator[ServiceRequest]:
        try:
            while True:
                yield self._queue.get(block=False)
                self._queue.task_done()
        except Empty:
            return

    def shutdown(self) -> None:
        if self._server:
            self.registry.unregister(self.address())
            self._server.shutdown()
            self._thread.join()
            self._thread = None

    def is_running(self) -> bool:
        return self._thread


class ServiceDispatcher(Protocol):
    def __call__(
        self,
        service: Service,
        handler: Callable[[ServiceRequest], None],
        poll: float = 0.5,
    ) -> ServiceController: ...


ServiceRequestHandler: TypeAlias = Callable[[ServiceRequest], None]


class Channel:
    registry: ClassVar[ServiceRegistry | None] = None
    Controller: ClassVar[ServiceDispatcher | None] = None

    def __init__(
        self,
        *,
        name: str,
        registry: ServiceRegistry | None = None,
        poll: float = 0.5,
        queue_size: int = 0,
        start: bool = True,
    ) -> None:
        cls = self.__class__
        self.registry = registry or cls.registry
        self.name = name
        self.poll = poll
        self.queue_size = queue_size
        self.start = start

        if not self.registry:
            msg = "No registry set"
            raise ValueError(msg)

        if not self.Controller:
            msg = "No controller set"
            raise RuntimeError(msg)

    def __call__(self, handler: Callable[[ServiceRequest], None]) -> ServiceController:
        service = self.registry.create_service(
            self.name,
            Queue(maxsize=self.queue_size),
            start=self.start,
        )
        return self.Controller(service, handler, self.poll)


class ServiceClient:
    def __init__(self, address: ServiceAddress) -> None:
        self.address = address

    def send(self, request: ServiceRequest, timeout: float | None = None) -> None:
        data = json.dumps(asdict(request)).encode("utf-8")
        url = f"http://{LOCALHOST}:{self.address.port}/"
        req = _request.Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with _request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    msg = f"Failed to send service request to {url}"
                    raise RuntimeError(msg)
        except error.HTTPError as ex:
            logger.exception(str(ex.args))
            raise


def find_channel_service(
    *,
    filter: list[str] | None = None,  # noqa: A002
    timeout: float = 5,
    maxcount: int = 0,
) -> list[ServiceAddress]:
    """
    Find services.

    Find services that match the given filter on the network using mDNS.

    :param filter: list of service names to filter by, defaults to None
    :param timeout: maximum time to wait for responses, defaults to 5 seconds
    :param maxcount: maximum number of services to return, defaults to 0 (unlimited)
    :return: list of ServiceAddress instances
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(DISCOVERY_SERVICE_ADDR)
    sock.setblocking(False)  # noqa: FBT003
    result = set()

    with suppress(TimeoutError):
        prefix = DISCOVERY_SERVICE_TYPE.encode("utf-8")
        start = time.time()
        while time.time() - start < timeout:
            sock.settimeout(timeout)
            data, addr = sock.recvfrom(1024)
            if data.startswith(prefix):
                service_addr = ServiceAddress.parse(data.decode("utf-8"))
                if filter is None or service_addr.name in filter:
                    result.add(service_addr)
                    if maxcount > 0 and len(result) >= maxcount:
                        break

    with suppress(Exception):
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()

    return list(result)


logger = getLogger("FreeCAD.Channels")

LOCALHOST = "127.0.0.1"

# Discovery service config
DISCOVERY_SERVICE_HOST = LOCALHOST
DISCOVERY_SERVICE_TYPE = "_freecad_channels._tcp.local."
DISCOVERY_SERVICE_PORT = 58987
DISCOVERY_SERVICE_ADDR = (DISCOVERY_SERVICE_HOST, DISCOVERY_SERVICE_PORT)

# Threads id sequence
TID = count(1)

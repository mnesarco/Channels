# SPDX-License: LGPL-3.0-or-later
# (c) 2024 Frank David Martínez Muñoz. <mnesarco at gmail.com>

from __future__ import annotations

from typing import Any, Protocol, TYPE_CHECKING
import FreeCAD as App  # type: ignore
from enum import Enum
from types import FunctionType

if TYPE_CHECKING:
    from .lang import dtr
    from collections.abc import Callable, Iterable


class Command:
    """
    Gui Command.
    """

    name: str
    _installed: bool
    _impl: Any

    def __init__(self, impl: Any, name: str) -> None:
        self._impl = impl
        self.name = name
        self._installed = False

    def install(self) -> None:
        if self._installed:
            return

        if not App.GuiUp:
            msg = "Commands requires Gui but Gui is not loaded"
            raise RuntimeError(msg)

        App.Gui.addCommand(self.name, self._impl)
        self._installed = True

    def __call__(self, item: int = 0) -> None:
        if not self._installed:
            msg = f"Command {self.name} is defined but not installed yet."
            raise RuntimeError(msg)

        App.Gui.runCommand(self.name, item)

    # Command is callable, so it can be used as cmd(), but also can be called as cmd.run()
    run = __call__

    def __str__(self) -> str:
        return self.name


class CommandProtocol(Protocol):
    """
    Class based commands protocol. All methods are optional.
    """

    def on_init(self) -> None: ...
    def on_activated(self, checked: bool | None = False) -> None: ...  # noqa: FBT002
    def is_active(self) -> bool: ...


class CommandType(Enum):
    """Command type ([FreeCAD API])"""

    AlterDoc = "AlterDoc"
    Alter3DView = "Alter3DView"
    AlterSelection = "AlterSelection"
    ForEdit = "ForEdit"
    NoTransaction = "NoTransaction"


class CommandRegistry:
    """Registry of commands"""

    _prefix: str
    _commands: dict[str, Command]
    _installed: bool

    def __init__(self, prefix: str = "") -> None:
        self._prefix = prefix
        self._commands = {}
        self._installed = False

    def install(self) -> None:
        if not App.GuiUp:
            msg = "Commands requires Gui but Gui is not loaded"
            raise RuntimeError(msg)

        for cmd in self._commands.values():
            cmd.install()
        self._installed = True

    def names(self) -> list[str]:
        return list(self._commands.keys())

    def add(
        self,
        *,
        label: str,
        tooltip: str = "",
        icon: str | None = None,
        accel: str | None = None,
        help_url: str | None = None,
        what_is_this: str | None = None,
        status_tip: str | None = None,
        checked: bool | None = None,
        exclusive: bool = False,
        dropdown: bool = False,
        cmd_type: Iterable[CommandType] | None = None,
        subcommands: list[str | Command] | None = None,
        default_subcommand: int | None = None,
        name: str | None = None,
        transaction: str | dtr | None = None,
        progress: str | dtr | None = None,
    ) -> Callable[[type], Command]:
        def deco(class_or_function: type | FunctionType) -> Command:
            if isinstance(class_or_function, FunctionType):

                class cls:
                    def on_activated(self, *args) -> None:
                        class_or_function(*args)

                name_suffix = name or class_or_function.__name__
            else:
                cls = class_or_function
                name_suffix = name or cls.__name__

            fq_name = f"{self._prefix}{name_suffix}"

            # [FreeCAD API] PythonCommand
            class PythonCommandImpl:
                def __init__(self) -> None:
                    self._impl = cls()
                    self.name = fq_name

                def GetResources(self) -> dict[str, str]:
                    res = {"MenuText": label, "ToolTip": tooltip}
                    if icon:
                        res["Pixmap"] = icon
                    if accel:
                        res["Accel"] = accel
                    if what_is_this:
                        res["WhatsThis"] = what_is_this
                    if status_tip:
                        res["StatusTip"] = status_tip
                    if checked is not None:
                        res["Checkable"] = checked
                    if exclusive:
                        res["Exclusive"] = exclusive
                    if dropdown:
                        res["DropDownMenu"] = dropdown
                    if cmd_type:
                        res["CmdType"] = ",".join(cmd_type)
                    return res

                if hasattr(cls, "is_active"):

                    def IsActive(self) -> bool:
                        return bool(self._impl.is_active())

                def ActivatedTx(self, *args) -> None:
                    in_transaction = False
                    if doc := App.activeDocument():
                        doc.openTransaction(str(transaction))
                        in_transaction = True
                    try:
                        self.ActivatedProgress(*args)
                    except Exception:
                        if in_transaction:
                            doc.abortTransaction()
                        raise
                    if in_transaction:
                        doc.commitTransaction()

                def ActivatedProgress(self, *args) -> None:
                    from . import fcui as ui

                    if progress:
                        with ui.progress_indicator(str(progress)):
                            self._impl.on_activated(*args)
                    else:
                        self._impl.on_activated(*args)

                if hasattr(cls, "on_activated"):
                    if transaction:
                        Activated = ActivatedTx
                    else:
                        Activated = ActivatedProgress

                if hasattr(cls, "on_init"):

                    def OnActionInit(self) -> None:
                        self._impl.on_init()

                if subcommands:

                    def GetCommands(self) -> list[str]:
                        return [c.name if isinstance(c, Command) else c for c in subcommands]

                    def GetDefaultCommand(self) -> int:
                        return default_subcommand or 0

                if help_url:

                    def CmdHelpURL(self) -> str | None:
                        return help_url

            command = Command(PythonCommandImpl(), fq_name)
            self._commands[fq_name] = command
            if self._installed:
                command.install()
            return command

        return deco

    def add_group(
        self,
        name: str,
        subcommands: list[str | Command],
        *,
        label: str,
        tooltip: str = "",
        icon: str | None = None,
        accel: str | None = None,
        help_url: str | None = None,
        what_is_this: str | None = None,
        status_tip: str | None = None,
        exclusive: bool = False,
        cmd_type: Iterable[CommandType] | None = None,
        default_subcommand: int | None = None,
    ) -> Callable[[type], Command]:
        if not subcommands:
            msg = "subcommands is missing or empty"
            raise ValueError(msg)

        @self.add(
            label=label,
            tooltip=tooltip,
            icon=icon,
            accel=accel,
            help_url=help_url,
            what_is_this=what_is_this,
            status_tip=status_tip,
            exclusive=exclusive,
            cmd_type=cmd_type,
            default_subcommand=default_subcommand,
            subcommands=subcommands,
            name=name,
        )
        class CmdGroup:
            pass

        return CmdGroup

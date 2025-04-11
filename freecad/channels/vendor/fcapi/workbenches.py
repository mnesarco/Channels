# SPDX-License: LGPL-3.0-or-later
# (c) 2024 Frank David Martínez Muñoz. <mnesarco at gmail.com>

from __future__ import annotations

from collections.abc import Iterable
from contextlib import suppress
from enum import Enum
from typing import Protocol, TypeAlias
from collections.abc import Callable

import FreeCAD as App  # type: ignore
import FreeCADGui as Gui  # type: ignore


class WithName(Protocol):
    """Typing: objects with name property"""

    @property
    def name(self): ...


class ToolSetTarget(Enum):
    """Toolset GUI target container"""

    Menu = 1
    ContextMenu = 2
    Toolbar = 3
    Commandbar = 4


class ToolSet:
    """Set of commands"""

    path: list[str]
    items: list[ToolSetItem]

    Separator = "Separator"

    def __init__(self, path: ToolSetPath = "", *commands: ToolSetItems) -> None:
        if isinstance(path, str):
            self.path = [path]
        else:
            self.path = [*path]
        self.items = []
        self.add(commands)

    def add(self, *items: ToolSetItems) -> None:
        _items = self.items
        for item in items:
            if isinstance(item, (str, ToolSet)):
                _items.append(item)
            elif hasattr(item, "name"):
                _items.append(item.name)
            else:
                self.add(*iter(item))

    def add_separator(self) -> None:
        self.items.append(self.Separator)

    def _install(
        self,
        installer: Callable,
        parent: list[str] | None = None,
        allow_nest: bool = True,
    ) -> None:
        if parent is None:
            path = self.path
        else:
            path = [*parent, *self.path]

        for item in self.items:
            if isinstance(item, str):
                if allow_nest:
                    installer(path, [item])
                else:
                    installer(self.path[0], [item])
            elif allow_nest:
                item._install(installer, path, allow_nest)

    def install(
        self,
        wb: Gui.Workbench,
        target: ToolSetTarget = ToolSetTarget.Menu,
    ) -> None:
        if target == ToolSetTarget.Menu:
            self._install(wb.appendMenu)
        elif target == ToolSetTarget.ContextMenu:
            self._install(wb.appendContextMenu)
        elif target == ToolSetTarget.Toolbar:
            self._install(wb.appendToolbar, allow_nest=False)
        elif target == ToolSetTarget.Commandbar:
            self._install(wb.appendCommandbar, allow_nest=False)


ToolSetPath: TypeAlias = str | list[str]
ToolSetItem: TypeAlias = str | ToolSet | WithName
ToolSetItems: TypeAlias = ToolSetItem | Iterable[ToolSetItem]


class Workbench:
    """Base Workbench class"""

    internal_workbench: Gui.Workbench

    Label: str = None
    MenuText: str = ""
    ToolTip: str = ""
    Icon: str = None  # path to the icon

    def on_init(self) -> None:
        pass

    def on_activated(self) -> None:
        pass

    def on_deactivated(self) -> None:
        pass

    def on_context_menu(self, recipient: str, menu: ToolSet) -> None:
        pass

    def name(self) -> str:
        return self.internal_workbench.name()

    def icon(self) -> str:
        return self.Icon

    def label(self) -> str:
        return self.MenuText

    def tooltip(self) -> str:
        return self.ToolTip

    def add_commandbar(self, bar: ToolSet) -> None:
        bar.install(self.internal_workbench, ToolSetTarget.Commandbar)

    def add_menu(self, menu: ToolSet) -> None:
        menu.install(self.internal_workbench, ToolSetTarget.Menu)

    def add_toolbar(self, toolbar: ToolSet) -> None:
        toolbar.install(self.internal_workbench, ToolSetTarget.Toolbar)

    def remove_commandbar(self, name: str) -> None:
        self.internal_workbench.removeCommandbar(name)

    def remove_menu(self, name: str) -> None:
        self.internal_workbench.removeMenu(name)

    def remove_toolbar(self, name: str) -> None:
        self.internal_workbench.removeToolbar(name)

    def activate(self) -> None:
        self.internal_workbench.activate()

    def reload_active(self) -> None:
        self.internal_workbench.reloadActive()

    def menus(self) -> list[str]:
        return self.internal_workbench.listMenus()

    def toolbars(self) -> list[str]:
        return self.internal_workbench.listToolbars()

    def toolbar_items(self) -> dict[str, list[str]]:
        return self.internal_workbench.getToolbarItems()

    def commandbars(self) -> list[str]:
        return self.internal_workbench.listCommandbars()

    @property
    def is_active(self) -> bool:
        return Gui.activeWorkbench() is self.internal_workbench

    @classmethod
    def install(
        cls,
        *,
        label: str | None = None,
        icon: str | None = None,
        tooltip: str | None = None,
        class_name: str | None = None,
    ) -> type[Gui.Workbench]:
        # [FreeCAD API] PythonWorkbench
        class WorkbenchWrapper(Gui.Workbench):
            MenuText: str = label or cls.Label or cls.MenuText
            ToolTip: str = tooltip or cls.ToolTip
            Icon: str = icon or cls.Icon

            def __init__(self) -> None:
                super().__init__()
                self._impl = cls()
                self._impl.internal_workbench = self

            def Initialize(self) -> None:
                self._impl.on_init()

            def Activated(self) -> None:
                self._impl.on_activated()

            def Deactivated(self) -> None:
                self._impl.on_deactivated()

            def ContextMenu(self, recipient: str) -> None:
                menu = ToolSet()
                self._impl.on_context_menu(recipient, menu)
                menu.install(self, ToolSetTarget.ContextMenu)

        WorkbenchWrapper.__name__ = class_name or f"{cls.__name__}Class"
        Gui.addWorkbench(WorkbenchWrapper)
        return WorkbenchWrapper


class RuleTarget(Enum):
    """Target container for Workbench Manipulator Rules"""

    MenuBar = 1
    ContextMenu = 2
    ToolBar = 3
    DockWindow = 4


class RuleActivationFn(Protocol):
    def __call__(self, *args) -> bool: ...


class BoolProducer(Protocol):
    def __call__(self) -> bool: ...


class Rule:
    """Workbench manipulator rule"""

    data: list[dict[str, str]]
    target: RuleTarget
    active: RuleActivationFn
    context: str | None

    def __init__(
        self,
        target: RuleTarget,
        data: list[dict[str, str]],
        context: str | None = None,
    ) -> None:
        self.target = target
        self.data = data
        self.active = lambda *_args: True
        self.context = context

    def condition(self, predicate: RuleActivationFn) -> RuleActivationFn:
        self.active = predicate
        return predicate

    __call__ = condition


class Rules:
    """Workbench Manipulator Rules"""

    data: list[Rule]
    name: str
    install_if_fn: BoolProducer

    def __init__(self, name: str):
        self.data = []
        self.name = name

    def menubar_insert(
        self,
        command: str,
        *,
        before: str | None = None,
        after: str | None = None,
    ) -> Rule:
        data = {
            "insert": command,
            "menuItem": before or after,
        }
        if after:
            data["after"] = True
        rule = Rule(RuleTarget.MenuBar, data)
        self.data.append(rule)
        return rule

    def menubar_append(self, command: str, *, sibling: str) -> Rule:
        data = {
            "append": command,
            "menuItem": sibling,
        }
        rule = Rule(RuleTarget.MenuBar, data)
        self.data.append(rule)
        return rule

    def menubar_remove(self, command: str) -> Rule:
        data = {
            "remove": command,
        }
        rule = Rule(RuleTarget.MenuBar, data)
        self.data.append(rule)
        return rule

    def context_menu_insert(
        self,
        command: str,
        *,
        before: str | None = None,
        after: str | None = None,
        recipient: str | None = None,
    ) -> Rule:
        data = {
            "insert": command,
            "menuItem": before or after,
        }
        if after:
            data["after"] = True
        rule = Rule(RuleTarget.ContextMenu, data, recipient)
        self.data.append(rule)
        return rule

    def context_menu_append(
        self,
        command: str,
        *,
        sibling: str,
        recipient: str | None = None,
    ) -> Rule:
        data = {
            "append": command,
            "menuItem": sibling,
        }
        rule = Rule(RuleTarget.ContextMenu, data, recipient)
        self.data.append(rule)
        return rule

    def context_menu_remove(
        self,
        command: str,
        recipient: str | None = None,
    ) -> Rule:
        data = {
            "remove": command,
        }
        rule = Rule(RuleTarget.ContextMenu, data, recipient)
        self.data.append(rule)
        return rule

    def toolbar_insert(self, command: str, *, before: str) -> Rule:
        data = {
            "insert": command,
            "toolItem": before,
        }
        rule = Rule(RuleTarget.ToolBar, data)
        self.data.append(rule)
        return rule

    def toolbar_append(self, command: str, *, toolbar: str) -> Rule:
        data = {
            "append": command,
            "toolBar": toolbar,
        }
        rule = Rule(RuleTarget.ToolBar, data)
        self.data.append(rule)
        return rule

    def toolbar_remove(
        self,
        *,
        command: str | None,
        toolbar: str | None = None,
    ) -> Rule:
        if command and toolbar:
            msg = "Specify command or toolbar but not both"
            raise ValueError(msg)
        if not command and not toolbar:
            msg = "command or toolbar is missing"
            raise ValueError(msg)

        data = {
            "remove": command or toolbar,
        }
        rule = Rule(RuleTarget.ToolBar, data)
        self.data.append(rule)
        return rule

    def install(self) -> None:
        if hasattr(Gui, self.name):
            msg = f"WorkbenchManipulator: {self.name} already installed.\n"
            App.Console.PrintDeveloperWarning(msg)
            return

        App.Console.PrintLog(f"Installing WorkbenchManipulator: {self.name}.\n")
        rules = self.data

        class WorkbenchManipulator:
            """[FreeCAD API] WorkbenchManipulator"""

            def modifyMenuBar(self):
                return [r.data for r in rules if r.target == RuleTarget.MenuBar and r.active()]

            def modifyContextMenu(self, recipient: str):
                return [
                    r.data
                    for r in rules
                    if r.target == RuleTarget.ContextMenu
                    and r.active(recipient)
                    and (r.context is None or r.context == recipient)
                ]

            def modifyToolBars(self):
                return [r.data for r in rules if r.target == RuleTarget.ToolBar and r.active()]

        wbm = WorkbenchManipulator()
        setattr(Gui, self.name, wbm)
        Gui.addWorkbenchManipulator(wbm)
        with suppress(Exception):
            Gui.activeWorkbench().reloadActive()

    def uninstall(self) -> None:
        if wbm := getattr(Gui, self.name, None):
            App.Console.PrintLog(f"Uninstalling WorkbenchManipulator: {self.name}.\n")
            Gui.removeWorkbenchManipulator(wbm)
            delattr(Gui, self.name)
            with suppress(Exception):
                Gui.activeWorkbench().reloadActive()

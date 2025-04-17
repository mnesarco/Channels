# SPDX-License: LGPL-3.0-or-later
# (c) 2024 Frank David Martínez Muñoz. <mnesarco at gmail.com>

# ruff: noqa: N801, A001

from __future__ import annotations

from functools import cached_property
import operator
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from itertools import filterfalse
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, ClassVar
from collections import defaultdict
import contextlib

import FreeCAD as App  # type: ignore

from .events import events
from .fpo import Preference, PreferencePreset, Preferences, _is
from .lang import dtr, translate

from PySide.QtCore import QObject  # type: ignore

if TYPE_CHECKING:
    from collections.abc import Callable
    from . import fcui as ui

    class PrefWidget(ui.QWidget, Protocol):
        """Preference editor widget"""

        _label: ui.QWidget

        def value(self) -> Any: ...
        def setValue(self, value: Any) -> None: ...

    GuiElementType = str | type
    GuiElement = Preference | str | dtr | ui.QWidget | tuple[Preference, GuiElementType] | None


class PreferencesPage(ABC):
    """Base class for all new PreferencePages"""

    @abstractmethod
    def build(self) -> ui.QWidget: ...

    @abstractmethod
    def on_save(self) -> None: ...

    @abstractmethod
    def on_load(self) -> None: ...


class PreferencesPageInstaller:
    """
    Create the FreeCAD PreferencesPage class and install it.
    """

    def __init__(self, group: str, impl: type[PreferencesPage]) -> None:
        """Create the FreeCAD PreferencesPage"""
        self.group: str = group
        self.impl: type[PreferencesPage] = impl
        self.installed: bool = False

    def install(self) -> bool:
        if self.installed:
            return True

        if not App.GuiUp:
            App.Console.PrintError(
                f"Installing preferences page: {self.group}/{self.impl.__qualname__} "
                "while Gui is not ready\n",
            )
            return False

        impl = self.impl

        # [FreeCAD API] PreferencesPage
        class PreferencesPageImpl:
            def __init__(self, _parent=None) -> None:
                self._impl = impl()
                self.form = self._impl.build()

            def saveSettings(self) -> None:
                self._impl.on_save()

            def loadSettings(self) -> None:
                self._impl.on_load()

        App.Console.PrintLog(f"Installing preferences page: {impl.__qualname__}\n")

        # FreeCAD uses __name__ as the internal key for pages
        PreferencesPageImpl.__name__ = f"{self.impl.__name__}Impl"
        App.Gui.addPreferencePage(PreferencesPageImpl, self.group)
        self.installed = True

        return self.installed


def preferences_page(*, group: str) -> Callable[[type[PreferencesPage]], PreferencesPageInstaller]:
    """
    Decorator to make a PreferencesPage installable in FreeCAD
    """

    def deco(page_class: type[PreferencesPage]) -> PreferencesPageInstaller:
        return PreferencesPageInstaller(group, page_class)

    return deco


class InvalidPreferenceTypeError(Exception):
    """Preference type does not have an associated editor widget"""


def pref_widget(
    pref: Preference,
    *,
    add: bool = True,
    builder: str | Callable | None = None,
) -> PrefWidget:
    """
    Create an UI widget for the preference based on its type.
    """
    from . import fcui as ui

    if pref.ui:
        builder = pref.ui

    if builder:
        if pref.value_type is not str:
            msg = "Preferences with custom builder must set value_type=str"
            raise ValueError(msg)

        _parser = pref.parser or (lambda x: x)
        if isinstance(builder, str):
            _builder = getattr(ui, builder)
            return _builder(
                value=_parser(pref()),
                label=f"{pref.label}:",
                add=add,
                toolTip=str(pref.description),
            )

        return builder(
            value=_parser(pref()),
            label=f"{pref.label}:",
            add=add,
            toolTip=str(pref.description),
        )

    if pref.options:
        return ui.InputOptions(
            options=pref.options,
            value=pref(),
            label=f"{pref.label}:",
            add=add,
            toolTip=str(pref.description),
        )

    if pref.value_type is bool:
        return ui.InputBoolean(
            value=pref(),
            label=f"{pref.label}:",
            add=add,
            toolTip=str(pref.description),
        )

    if pref.unit:
        return ui.InputQuantity(
            value=f"{pref()}{pref.unit}",
            label=f"{pref.label}:",
            stretch=0.5,
            unit=pref.unit,
            add=add,
            toolTip=str(pref.description),
        )

    if pref.value_type is int:
        return ui.InputInt(
            value=pref(),
            label=f"{pref.label}:",
            add=add,
            toolTip=str(pref.description),
        )

    if pref.value_type is float:
        return ui.InputFloat(
            value=pref(),
            label=f"{pref.label}:",
            add=add,
            toolTip=str(pref.description),
        )

    if pref.value_type is str:
        return ui.InputText(
            value=pref(),
            label=f"{pref.label}:",
            add=add,
            toolTip=str(pref.description),
        )

    msg = f"Preference type {pref.value_type} does not have an associated editor widget"
    raise InvalidPreferenceTypeError(msg)


@dataclass
class _ValidationError(Exception):
    message: str


class AutoGui(QObject):
    """
    Generated GUI for Preferences Pages
    """

    title: str | dtr
    form: ui.QWidget
    selector: PresetSelector
    widgets: list[tuple[PrefWidget, PreferencePreset]]
    sections: list[tuple[ui.QGroupBox, dtr | str]]
    container: ui.QWidget | None = None

    def __init__(
        self,
        title: str | dtr,
        elements: Callable[[], list[GuiElement]] | list[GuiElement],
    ) -> None:
        from . import fcui as ui

        super().__init__()

        items = elements() if callable(elements) else elements
        widgets: list[tuple[PrefWidget, PreferencePreset]] = []
        sections: list[tuple[ui.QGroupBox, dtr | str]] = []

        margins = ui.margins()
        with ui.Container(windowTitle=str(title), contentsMargins=margins) as form:
            with ui.GroupBox(contentsMargins=margins, title=str(dtr("Preferences", "Preset"))):
                selector = PresetSelector(items, widgets)
            section: ui.GroupBox = None
            for item in items:
                if isinstance(item, Preference):
                    widget = pref_widget(item)
                    setup_validators(widget, item)
                    widgets.append((widget, item.preset("Default")))
                elif isinstance(item, tuple):
                    _item, _input, *_ = item
                    widget = pref_widget(_item, builder=_input)
                    setup_validators(widget, item)
                    widgets.append((widget, _item.preset("Default")))
                elif isinstance(item, (str, dtr)):
                    if section:
                        section.__exit__(None, None, None)
                    ui.Spacing(15)
                    section = ui.GroupBox(title=str(item), contentsMargins=margins)
                    sections.append((section.__enter__(), item))
                elif isinstance(item, ui.QWidget):
                    ui.place_widget(item)
            if section:
                section.__exit__(None, None, None)
            ui.Stretch()

        form.onLanguageChange.connect(self.apply_translations)

        self.title = title
        self.form = form
        self.selector = selector
        self.widgets = widgets
        self.sections = sections

    def apply_translations(self) -> None:
        from . import fcui as ui

        self.form.setWindowTitle(str(self.title))
        for w, p in self.widgets:
            if label := getattr(w, "_label", None):
                label.setText(str(p.preference.label))
                if tt := getattr(w, "setToolTip", None):
                    tt(str(p.preference.description))
                if isinstance(w, ui.QComboBox) and p.preference.options:
                    for i, text in enumerate(p.preference.options.keys()):
                        w.setItemText(i, str(text))

        for w, text in self.sections:
            w.setTitle(str(text))

        self.selector.apply_translations()

        if self.container is None:
            # Store parent to prevent triggering a bug in qt 6.8
            # https://bugreports.qt.io/projects/PYSIDE/issues/PYSIDE-2711?filter=allissues
            self.container = self.form.parentWidget()

        if self.container:
            self.container.setWindowTitle(str(self.title))

    def load(self) -> None:
        self.selector.on_preset_change()

    def validate(self) -> None:
        for widget, _pref in self.widgets:
            with contextlib.suppress(AttributeError):
                widget._label.clearNotification()  # noqa: SLF001

        messages = []
        for widget, pref in self.widgets:
            value = widget.value()
            if validators := pref.preference.ui_validators:
                for v in validators:
                    if msg := v.validate(value):
                        with contextlib.suppress(AttributeError):
                            widget._label.setNotification("dialog-warning", msg)  # noqa: SLF001
                        messages.append(f"{pref.preference.label}: {msg}")

        if messages:
            raise _ValidationError("\n".join(messages))

    def save_as(self, new_preset: str) -> None:
        for widget, pref in self.widgets:
            target = pref.preference.preset(new_preset)
            target(update=widget.value())
        self.selector.input.addOption(new_preset, new_preset)

    def delete(self, preset: str) -> None:
        groups = set()
        for _, pref in self.widgets:
            groups.add(pref.preference.group_key)
        for g in groups:
            if (param := App.ParamGet(f"{g}/presets")) and param.HasGroup(preset):
                param.RemGroup(preset)
        self.selector.input.removeOption(preset)

    def update_preset_list(self, selected: str | None = None) -> None:
        if not selected:
            selected = next(iter(self.selector.input.values()))
        self.selector.selected = selected

    def save(self) -> None:
        action = self.selector.action
        preset = self.selector.selected
        new_preset = self.selector.new_name

        if action == "save_as":
            self.validate()
            if not (new_preset and preset != new_preset):
                msg = translate("Preferences", "New preset name must be different")
                raise _ValidationError(msg)
            self.save_as(new_preset)
            self.update_preset_list(new_preset)
            self.selector.action = "none"
            return

        if action == "rename":
            self.validate()
            if not (new_preset and preset != new_preset):
                msg = translate("Preferences", "New preset name must be different")
                raise _ValidationError(msg)
            if preset == "Default":
                msg = translate("Preferences", "Default preset cannot be renamed")
                raise _ValidationError(msg)
            self.save_as(new_preset)
            self.update_preset_list(new_preset)
            self.delete(preset)
            self.update_preset_list(new_preset)
            self.selector.action = "none"
            return

        if action == "delete":
            if preset == "Default":
                msg = translate("Preferences", "Default preset cannot be removed")
                raise _ValidationError(msg)
            self.delete(preset)
            self.update_preset_list()
            self.selector.action = "none"
            return

        self.validate()
        for widget, pref in self.widgets:
            pref(update=widget.value())
        self.selector.action = "none"


class PresetSelector:
    """
    Widget to select, rename, copy and delete Presets.
    """

    input: PrefWidget
    actions: PrefWidget
    name: PrefWidget
    preferences: list[Preference]
    widgets: list[tuple[PrefWidget, PreferencePreset]]

    action_options: ClassVar[dict[dtr, str]] = {
        dtr("Preferences", "Preset action:"): "none",
        dtr("Preferences", "Save preset as:"): "save_as",
        dtr("Preferences", "Rename preset to:"): "rename",
        dtr("Preferences", "Delete preset:"): "delete",
    }

    def __init__(self, items: list, widgets: list[tuple[PrefWidget, PreferencePreset]]) -> None:
        from . import fcui as ui

        self.preferences = list(filter(_is(Preference), items))
        self.widgets = widgets

        presets = self.preset_names()
        self.input = ui.InputOptions(
            options={v: v for v in presets},
            value=None,
            label=translate("Preferences", "Preset:"),
        )
        self.input.currentIndexChanged.connect(self.on_preset_change)

        with ui.Row(ContentsMargins=ui.margins()):
            self.actions = ui.InputOptions(self.action_options)
            self.actions.currentIndexChanged.connect(self.on_action_change)
            self.name = ui.InputText(translate("Preferences", "Update current preset"))

        if presets:
            self.input.setValue(presets[0])
        else:
            self.input.setValue("Default")

    def apply_translations(self) -> None:
        self.input._label.setText(translate("Preferences", "Preset:"))  # noqa: SLF001
        actions = self.actions
        for i, (text, _val) in enumerate(self.action_options.items()):
            actions.setItemText(i, str(text))
        self.on_action_change()

    def on_action_change(self, *_) -> None:
        from .fcui import set_indicator_icon

        preset = self.input.value()
        action = self.actions.value()
        name_input = self.name
        name_input.setStyleSheet("")
        name_input.repaint()
        name_input.setReadOnly(True)
        name_input.setValue("")
        set_indicator_icon(name_input, None)

        if action == "save_as":
            name_input.setReadOnly(False)
            name_input.setFocus()

        elif action == "rename":
            if preset == "Default":
                self.actions.setValue("save_as")
                return
            name_input.setReadOnly(False)
            name_input.setFocus()

        elif action == "none":
            name_input.setValue(translate("Preferences", "Update current preset"))

        elif action == "delete":
            if preset == "Default":
                self.actions.setValue("save_as")
                return
            name_input.setValue(translate("Preferences", "Delete current preset"))
            name_input.setStyleSheet("QLineEdit { background-color : red; color : white; }")
            set_indicator_icon(name_input, "dialog-warning")
            name_input.repaint()

    def on_preset_change(self, *_) -> None:
        selected = self.input.value()
        if selected is None:
            self.input.setValue("Default")
            return

        self.on_action_change()
        widgets = self.widgets
        for i, (w, p) in enumerate(widgets):
            preset = p.preference.preset(selected)
            widgets[i] = w, preset
            w.setValue(preset())

    def preset_names(self) -> list[str]:
        presets: set[str] = {"Default"}
        update = presets.update
        for p in self.preferences:
            update(p.preset_names())
        return sorted(presets)

    @property
    def selected(self) -> str:
        return self.input.value()

    @selected.setter
    def selected(self, value: str) -> None:
        self.input.setValue(value)
        self.actions.setValue("none")

    @property
    def new_name(self) -> str:
        v = self.name.value()
        return v.strip() if v else None

    @property
    def action(self) -> str:
        return self.actions.value()

    @action.setter
    def action(self, value: str) -> str:
        return self.actions.setValue(value)


def setup_validators(widget: object, pref: Preference) -> None:
    """Enhance widgets with validation constraints if possible"""
    if validators := pref.ui_validators:
        for v in validators:
            v.setup(widget)


def make_preferences_page(
    *,
    group: str,
    title: str | dtr,
    elements: Callable[[], list[GuiElement]] | list[GuiElement],
) -> type[PreferencesPage]:
    """
    Dynamically create a Preferences Page
    """

    class Page(PreferencesPage):
        def build(self) -> ui.QWidget:
            if (gui := getattr(self, "gui", None)) is None:
                gui = AutoGui(title, elements)
                self.gui = gui
            return gui.form

        def on_load(self) -> None:
            App.Console.PrintLog(f"Loading preferences: {group}/{title}\n")
            self.gui.load()

        def on_save(self) -> None:
            try:
                self.gui.save()
                App.Console.PrintLog(f"Saved preferences: {group}/{title}\n")
            except _ValidationError as err:
                from .fcui import show_error

                App.Console.PrintLog(f"Error saving preferences: {group}/{title}\n{err.message}\n")
                show_error(err.message, f"{group}/{title}")

    Page.__name__ = f"_{uuid.uuid4()}"
    return Page


def basic_preferences_page(*, group: str, title: str | dtr):
    """
    Decorator to take a list of GuiElements returned from a function and build a Page.
    """

    def deco(
        elements: Callable[[], list[GuiElement]] | list[GuiElement],
    ) -> PreferencesPageInstaller:
        page = make_preferences_page(group=group, title=title, elements=elements)
        return preferences_page(group=group)(page)

    return deco


_P = TypeVar("_P")


class auto_gui:
    """
    Decorator to generate and install PreferencePages in main FreeCAD Preferences editor.
    """

    def __init__(
        self,
        *,
        default_ui_group: str,
        default_ui_page: str | dtr,
        install: bool = True,
    ) -> None:
        """Generate and install PreferencePages in main FreeCAD Preferences editor"""
        self.cls = None
        self.default_ui_group = default_ui_group
        self.default_ui_page = default_ui_page
        self.install = install
        self.installed = False

    def __call__(self, cls: _P) -> _P:
        if not issubclass(cls, Preferences):
            msg = "@auto_gui decorator is only allowed on Preferences subclasses"
            raise TypeError(msg)
        self.cls = cls
        cls._gui = self
        return cls

    @cached_property
    def ui_preferences(self) -> list[Preference]:
        """Non excluded preferences"""
        preferences = map(operator.itemgetter(1), self.cls.declared_preferences())
        excluded = operator.attrgetter("ui_exclude")
        return list(filterfalse(excluded, preferences))

    @cached_property
    def ui_groups(self) -> dict[str, dict[str, list[Any]]]:
        """
        Build the structure with all groups, pages, sections, and preferences.

        Assign ui_group and ui_page values if missing to be ready to sort correctly.
        ui_group and ui_page are inherited from the previous declared preference.
        default_ui_group and default_ui_page are used if not previous one.
        """
        preferences = self.ui_preferences
        groups: dict[str, dict[str, list[Any]]] = {}
        get_group = operator.attrgetter("ui_group")
        get_page = operator.attrgetter("ui_page")
        get_section = operator.attrgetter("ui_section")

        # Inherit ui_group, ui_page
        default_ui_group = self.default_ui_group
        default_ui_page = self.default_ui_page
        group = None
        page = None
        for pref in preferences:
            if not (new_group := get_group(pref)):
                pref.ui_group = group or default_ui_group
            if group != new_group:
                page = None
            group = get_group(pref)
            if not get_page(pref):
                pref.ui_page = page or default_ui_page
            page = get_page(pref)
            if g := groups.get(group):
                if page not in g:
                    g[page] = []
            else:
                groups[group] = {page: []}

        # Sort and add Preferences and sections to their pages
        sort_key = operator.attrgetter("ui_group", "ui_page", "ui_section", "label")
        preferences = sorted(preferences, key=sort_key)
        section = None
        for pref in preferences:
            group = groups.get(get_group(pref))
            page = group.get(get_page(pref))
            if (s := get_section(pref)) and s != section:
                section = s
                page.append(s)
            page.append(pref)

        return groups

    def ui_builders(self) -> dict[str, list[Callable[[], AutoGui]]]:
        gui = defaultdict(list)
        for group, pages in self.ui_groups.items():
            for page, items in pages.items():
                gui[group].append(lambda p=page, i=items: AutoGui(p, i))
        return gui

    @events.app.gui_up
    def on_gui(self, _event) -> None:
        """Install pages when GUI is ready"""
        if self.install and not self.installed:
            self.installed = True
            for group, pages in self.ui_groups.items():
                for page, items in pages.items():
                    build = basic_preferences_page(group=group, title=page)
                    build(items).install()


class validators:
    """Namespace of validators."""

    class min:
        """Validate minimum value"""

        def __init__(self, limit: float, *, excluded: bool = False) -> None:
            self.limit = limit
            if excluded:
                self.op = operator.le
                self.sym = ">"
            else:
                self.op = operator.lt
                self.sym = ">="

        def setup(self, ui: object) -> None:
            if setter := getattr(ui, "setMinimum", None):
                setter(self.limit)

        def validate(self, value: Any) -> str | None:
            if value is not None and self.op(value, self.limit):
                msg = translate("Validation", "Minimum accepted value is {} {}")
                return msg.format(self.sym, self.limit)
            return None

    class max:
        """Validate maximum value"""

        def __init__(self, limit: float, *, excluded: bool = False) -> None:
            self.limit = limit
            if excluded:
                self.op = operator.ge
                self.sym = "<"
            else:
                self.op = operator.gt
                self.sym = "<="

        def setup(self, ui: object) -> None:
            if setter := getattr(ui, "setMaximum", None):
                setter(self.limit)

        def validate(self, value: Any) -> str | None:
            if value is not None and self.op(value, self.limit):
                msg = translate("Validation", "Maximum accepted value is {} {}")
                return msg.format(self.sym, self.limit)
            return None

    class max_length:
        """Validate maximum length"""

        def __init__(self, limit: int) -> None:
            self.limit = limit

        def setup(self, ui: object) -> None:
            if setter := getattr(ui, "setMaxLength", None):
                setter(self.limit)

        def validate(self, value: Any) -> str | None:
            if value and len(value) > self.limit:
                msg = translate("Validation", "Maximum accepted length is {}")
                return msg.format(self.limit)
            return None

    class min_length:
        """Validate minimum length"""

        def __init__(self, limit: int) -> None:
            self.limit = limit

        def setup(self, _ui: object) -> None:
            pass

        def validate(self, value: Any) -> str | None:
            if not value or len(value) < self.limit:
                msg = translate("Validation", "Minimum accepted length is {}")
                return msg.format(self.limit)
            return None

    class required:
        """Validate required value"""

        def setup(self, ui: object) -> None:
            pass

        def validate(self, value: Any) -> str | None:
            if value is None or str(value).strip() == "":
                return translate("Validation", "Required")
            return None

    class regex:
        """Validate string value by regex"""

        def __init__(self, pattern: str) -> None:
            import re

            self.re = re.compile(pattern)

        def setup(self, _ui: object) -> None:
            pass

        def validate(self, value: str) -> None | str:
            if not value:
                return None
            if self.re.fullmatch(value) is None:
                return translate("Validation", "Invalid format")
            return None

    positive = min(limit=0.0, excluded=True)
    negative = max(limit=0.0, excluded=True)


def gui_pages(cls: type[Preferences]) -> dict[str, list[Callable[[], AutoGui]]]:
    gui: auto_gui = getattr(cls, "_gui", None)
    if gui:
        return gui.ui_builders()
    return {}

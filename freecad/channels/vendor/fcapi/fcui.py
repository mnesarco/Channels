# SPDX-License: LGPL-3.0-or-later
# (c) 2024 Frank David Martínez Muñoz. <mnesarco at gmail.com>

"""Declarative Qt Gui Builders for FreeCAD."""

# ruff: noqa: D401, D105, D107, D413, D102
# ruff: noqa: PD013
# ruff: noqa: SIM105, SIM117, ANN401, PTH123, PLR0913 PLR0912, C901
# ruff: noqa: N802, N815, N806, N801
# ruff: noqa: A002

from __future__ import annotations

__author__ = "Frank David Martínez Muñoz"
__copyright__ = "(c) 2024 Frank David Martínez Muñoz."
__license__ = "LGPL 2.1"
__version__ = "1.0.0-beta5"
__min_python__ = "3.10"
__min_freecad__ = "0.22"

# Conventions for sections in this file:
# See: vscode extension: aaron-bond.better-comments
# ──────────────────────────────────────────────────────────────────────────────
#   Normal comments
##: Code execute at import time, create objects in global module scope
##$ Template code, meta-programming
##@ Decorators code
##% Type definitions, Widgets, Builders
##! Warning note
# ──────────────────────────────────────────────────────────────────────────────

##: [SECTION] Builtin Imports
##: ────────────────────────────────────────────────────────────────────────────

import json
import re
import sys
import threading
from contextlib import contextmanager
from functools import wraps, update_wrapper
from pathlib import Path
from typing import (
    Any,
    ClassVar,
    Protocol,
    TypeAlias,
    TYPE_CHECKING,
)


##: [SECTION] FreeCAD Imports
##: ────────────────────────────────────────────────────────────────────────────

import FreeCAD as App  # type: ignore[all]
import FreeCADGui as Gui  # type: ignore[all]
from FreeCAD import Base, DocumentObject  # type: ignore[all]

##: [SECTION] Qt/PySide Imports (Development)
##: ────────────────────────────────────────────────────────────────────────────
if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Hashable, Iterable, Iterator
    from PySide6.QtCore import (
        QMargins,
        QObject,
        QPoint,
        QRect,
        QSize,
        Qt,
        QTimer,
        Signal,
        SignalInstance,
        Slot,
        QEvent,
    )

    from PySide6.QtGui import (
        QAction,
        QActionGroup,
        QBrush,
        QCloseEvent,
        QColor,
        QFontDatabase,
        QIcon,
        QMoveEvent,
        QResizeEvent,
        QPainter,
        QPaintEvent,
        QPen,
        QPixmap,
        QTextCursor,
        QKeyEvent,
    )

    from PySide6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QComboBox,
        QColorDialog,
        QDialog,
        QDoubleSpinBox,
        QFileDialog,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLayout,
        QLineEdit,
        QTextEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QAbstractButton,
        QScrollArea,
        QSpinBox,
        QSplitter,
        QStackedLayout,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QToolButton,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
        QSizePolicy,
    )

    from PySide6.QtSvg import QSvgRenderer


##: [SECTION] Qt/PySide Imports (FreeCAD runtime)
##: ────────────────────────────────────────────────────────────────────────────
if not TYPE_CHECKING:
    from PySide.QtCore import (  # type: ignore[attr-defined]
        QMargins,
        QObject,
        QPoint,
        QRect,
        QSize,
        Qt,
        QTimer,
        Signal,
        Slot,
        QEvent,
    )

    from PySide.QtGui import (  # type: ignore[attr-defined]
        QAction,  # noqa: F401
        QActionGroup,  # noqa: F401
        QAbstractItemView,
        QApplication,
        QBrush,
        QCheckBox,
        QCloseEvent,
        QColor,
        QComboBox,
        QColorDialog,
        QDialog,
        QDoubleSpinBox,
        QFileDialog,
        QFontDatabase,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QIcon,
        QLabel,
        QLayout,
        QLineEdit,
        QTextEdit,
        QMainWindow,
        QMessageBox,
        QMoveEvent,
        QResizeEvent,
        QPainter,
        QPaintEvent,
        QPen,
        QPixmap,
        QPlainTextEdit,
        QPushButton,
        QAbstractButton,
        QScrollArea,
        QSpinBox,
        QSplitter,
        QStackedLayout,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QToolButton,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
        QSizePolicy,
        QTextCursor,
        QKeyEvent,
    )

    from PySide.QtSvg import QSvgRenderer  # type: ignore[attr-defined]


##: [SECTION] Type Aliases
##: ────────────────────────────────────────────────────────────────────────────

Numeric: TypeAlias = int | float
Vector: TypeAlias = Base.Vector
KwArgs: TypeAlias = dict[str, Any]

##: [SECTION] Core Widgets, Contexts and Decorators
##: ────────────────────────────────────────────────────────────────────────────

DEFAULT_ALIGNMENT = Qt.Alignment()


# ──────────────────────────────────────────────────────────────────────────────
def set_qt_attrs(qobject: QObject, **kwargs: KwArgs) -> None:
    """
    Call setters on Qt objects by argument names.

    :param QObject qobject: Object instance.
    :param dict[str, Any] kwargs: dict of property_name to value.
    """
    for name, value in kwargs.items():
        if value is not None:
            if name == "properties":
                for prop_name, prop_value in value.items():
                    qobject.setProperty(prop_name, prop_value)
                continue
            setter = getattr(qobject, f"set{name[0].upper()}{name[1:]}", None)
            if setter:
                if isinstance(value, tuple):
                    setter(*value)
                else:
                    setter(value)
            else:
                msg = f"Invalid property {name}"
                raise NameError(msg)


# ──────────────────────────────────────────────────────────────────────────────
def setup_layout(
    layout: QLayout,
    *,
    add: bool = True,
    **kwargs: KwArgs,
) -> Generator[QWidget, Any, None]:
    """Setup layout and add wrapper widget if required."""
    set_qt_attrs(layout, **kwargs)

    if  add is False or build_context().current().layout() is not None:
        w = QWidget()
        w.setContentsMargins(0, 0, 0, 0)
        w.setLayout(layout)
        if add:
            parent = build_context().current()
            parent.layout().addWidget(w)
        else:
            parent = w
        with build_context().stack(w):
            yield w
    else:
        parent = build_context().current()
        parent.setLayout(layout)
        yield parent


# ──────────────────────────────────────────────────────────────────────────────
def place_widget(
    widget: QWidget,
    label: QWidget | str = None,
    stretch: int = 0,
    alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
) -> None:
    """Place widget in layout."""
    current = build_context().current()
    if isinstance(current, QScrollArea):
        if current.widget():
            msg = "Scroll can contains only one widget"
            raise ValueError(msg)
        current.setWidget(widget)
        return

    if isinstance(current, QSplitter):
        current.addWidget(widget)
        return

    if isinstance(current, QMainWindow):
        current.setCentralWidget(widget)
        return

    layout = current.layout()
    if layout is None:
        layout = build_context().default_layout_provider()
        current.setLayout(layout)

    if isinstance(layout, QStackedLayout):
        layout.addWidget(widget)
        return

    if label is None:
        layout.addWidget(widget, stretch, alignment)
    else:
        layout.addWidget(widget_with_label_row(widget, label, stretch, alignment))


##% [Widget] QWidget with label and widget in Vertical or Horizontal layout
##% ────────────────────────────────────────────────────────────────────────────
def widget_with_label_row(
    widget: QWidget,
    label: QWidget | str,
    stretch: int = 0,
    alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
    orientation: Qt.Orientation = Qt.Orientation.Horizontal,
) -> QWidget:
    """Create a widget with a label and widget."""
    row = QWidget()
    layout = QVBoxLayout() if orientation == Qt.Orientation.Vertical else QHBoxLayout()
    row.setLayout(layout)
    layout.setContentsMargins(0, 0, 0, 0)
    if isinstance(label, QWidget):
        layout.addWidget(label)
        widget._label = label  # noqa: SLF001
    elif label:
        label = LabelEx(str(label))
        layout.addWidget(label)
        widget._label = label  # noqa: SLF001
    layout.addWidget(widget, stretch, alignment)
    return row


##% Color
##% ────────────────────────────────────────────────────────────────────────────
class Color(QColor):
    """
    QColor with additional constructor for hex rgba color code.

    Use like Color(code='#ff0000'), Color(code='#ff0000ff'), Color(code='#ff0000', alpha=0.5)
    """

    RGBA_RE = re.compile(r"rgba\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)")

    def __init__(
        self,
        *args: tuple,
        code: str | None = None,
        alpha: float | None = None,
        **kwargs: KwArgs,
    ) -> None:
        if code is not None:
            if code.startswith("#"):  # noqa: FURB188
                code = code[1:]
            if len(code) < 8:  # noqa: PLR2004
                code += "FFFFFFFF"
            r, g, b, a = (
                int(code[:2], 16),
                int(code[2:4], 16),
                int(code[4:6], 16),
                int(code[6:8], 16),
            )
            super().__init__(r, g, b, a)
        elif len(args) == 1 and isinstance(args[0], QColor):
            super().__init__()
            self.setRgba(args[0].rgba())
        elif len(args) == 1 and (rgba := self.RGBA_RE.fullmatch(args[0])):
            super().__init__(*(int(v) for v in rgba.groups()))
        else:
            try:
                super().__init__(*args, **kwargs)
            except Exception:  # noqa: BLE001
                super().__init__()

        if isinstance(alpha, float):
            self.setAlphaF(alpha)

    def __str__(self) -> str:
        return f"rgba({self.red()},{self.green()},{self.blue()},{self.alpha()})"

    def rgb_and_alpha(self) -> tuple[str, int]:
        return f"rgb({self.red()},{self.green()},{self.blue()})", self.alpha()


##% [Widget] ColorIcon
##% ────────────────────────────────────────────────────────────────────────────
class ColorIcon(QIcon):
    """Monochromatic Icon with transparent background."""

    def __init__(self, path: str | Path, color: QColor) -> None:
        pixmap = QPixmap(path)
        mask = pixmap.createMaskFromColor(QColor("transparent"), Qt.MaskInColor)
        pixmap.fill(color)
        pixmap.setMask(mask)
        super().__init__(pixmap)
        self.setIsMask(True)


##% PySignal
##% ───────────────────────────────────────────────────────────────────────────
class PySignal:
    """Imitate Qt Signals for non QObject objects."""

    _listeners: set[Callable]

    def __init__(self) -> None:
        self._listeners = set()

    def connect(self, listener: Callable) -> None:
        """Add listener."""
        self._listeners.add(listener)

    def disconnect(self, listener: Callable) -> None:
        """Remove listener."""
        try:
            self._listeners.remove(listener)
        except KeyError:
            pass  # Not found, Ok

    def emit(self, *args: tuple, **kwargs: KwArgs) -> None:
        """Trigger the signal."""
        for listener in self._listeners:
            listener(*args, **kwargs)


##@ [Decorator] on_event
##@ ────────────────────────────────────────────────────────────────────────────
def on_event(
    target: QObject | Signal | Iterable[QObject | Signal],
    event: str | None = None,
) -> Callable[[Callable], Callable]:
    """
    Event binder decorator.

    Connects the decorated function to `event` signal on all targets.

    :param QObject | Signal | list[QObject|Signal] target: target object or objects.
    :param str event: name of the signal.
    """
    if not target:
        msg = "Invalid empty target"
        raise ValueError(msg)

    if not isinstance(target, (list, tuple, set)):
        target = [target]

    if event is None:

        def deco(fn: Callable) -> Callable:
            for t in target:
                t.connect(fn)
            return fn

    else:

        def deco(fn: Callable) -> Callable:
            for t in target:
                getattr(t, event).connect(fn)
            return fn

    return deco


##% SelectedObject
##% ────────────────────────────────────────────────────────────────────────────
class SelectedObject:
    """Store Selection information of a single object+sub."""

    def __init__(
        self,
        doc: str,
        obj: str,
        sub: str | None = None,
        pnt: Vector | None = None,
    ) -> None:
        self.doc = doc
        self.obj = obj
        self.sub = sub
        self.pnt = pnt

    def __iter__(self) -> Iterator:
        yield App.getDocument(self.doc).getObject(self.obj)
        yield self.sub
        yield self.pnt

    def __repr__(self) -> str:
        return f"{self.doc}#{self.obj}.{self.sub}"

    def __hash__(self) -> int:
        return hash((self.doc, self.obj, self.sub))

    def __eq__(self, _o: object) -> bool:
        return hash(self) == hash(_o)

    def __ne__(self, _o: object) -> bool:
        return not self.__eq__(_o)

    def resolve_object(self) -> DocumentObject:
        """Resolve selection to actual DocumentObject."""
        return App.getDocument(self.doc).getObject(self.obj)

    def resolve_sub(self) -> Any:
        """Resolve selection to actual sub object."""
        return getattr(self.resolve_object(), self.sub)


# ──────────────────────────────────────────────────────────────────────────────
def register_select_observer(owner: QWidget, observer: Any) -> None:
    """Add observer with auto remove on owner destroyed."""
    Gui.Selection.addObserver(observer)

    def destroyed(*_args) -> None:
        Gui.Selection.removeObserver(observer)

    owner.destroyed.connect(destroyed)


# [Context] selection
# ──────────────────────────────────────────────────────────────────────────────
@contextmanager
def selection(
    *names: tuple,
    clean: bool = True,
    doc: App.Document = None,
) -> Generator[list[DocumentObject], None, None]:
    """
    Add objects identified by names into current selection.

    :param bool clean: remove selection at the end, defaults to True
    :param App.Document doc: Document, defaults to App.ActiveDocument
    :yield list[DocumentObject]: list of selected objects.
    """
    sel = Gui.Selection
    try:
        doc_name = (doc or App.ActiveDocument).Name
        if len(names) == 0:
            yield sel.getSelection(doc_name)
        else:
            sel.clearSelection()
            for name in names:
                if isinstance(name, (tuple, list)):
                    sel.addSelection(doc_name, *name)
                elif isinstance(name, SelectedObject):
                    sel.addSelection(name.doc, name.obj, name.sub)
                else:
                    sel.addSelection(doc_name, name)
            yield sel.getSelection(doc_name)
    finally:
        if clean:
            sel.clearSelection()


##% BuildContext class
##% ────────────────────────────────────────────────────────────────────────────
class _BuildContext:
    """Qt Widget tree build context and stack."""

    def __init__(self) -> None:
        self._stack = []
        self.default_layout_provider = QVBoxLayout

    def push(self, widget: QWidget) -> None:
        self._stack.append(widget)

    def pop(self) -> None:
        self._stack.pop()

    def reset(self) -> QWidget:
        last = self._stack[-1] if self._stack else None
        self._stack = []
        return last

    @contextmanager
    def stack(self, widget: QWidget) -> Generator[QWidget, None, None]:
        self.push(widget)
        try:
            yield widget
        finally:
            self.pop()

    @contextmanager
    def parent(self) -> Generator[QWidget, None, None]:
        if len(self._stack) > 1:
            current = self._stack[-1]
            self._stack.pop()
            parent = self._stack[-1]
            try:
                yield parent
            finally:
                self._stack.append(current)

    def current(self) -> QWidget:
        return self._stack[-1]

    def dump(self) -> None:
        print_log(f"BuildContext: {self._stack}")

    def is_empty(self) -> bool:
        return not bool(self._stack)


# ──────────────────────────────────────────────────────────────────────────────
def build_context() -> _BuildContext:
    """Build context for the current thread."""
    bc = getattr(_thread_local_gui_vars, "BuildContext", None)
    if bc is None:
        _thread_local_gui_vars.BuildContext = _BuildContext()
        return _thread_local_gui_vars.BuildContext
    return bc


##% [Context] Parent
##% ────────────────────────────────────────────────────────────────────────────
@contextmanager
def Parent() -> Generator[QWidget, None, None]:
    """Put parent in context"""
    with build_context().parent() as p:
        yield p


##% Dialogs
##% ────────────────────────────────────────────────────────────────────────────
class Dialogs:
    """Keeps a list of Active dialogs."""

    _list: ClassVar[list[QWidget]] = []

    @classmethod
    def dump(cls) -> None:
        """Dump active dialogs to console."""
        print_log(f"Dialogs: {cls._list}")

    @classmethod
    def register(cls, dialog: QWidget) -> None:
        """Register an active dialog."""
        cls._list.append(dialog)
        dialog.closeEvent = lambda _e: cls.destroy_dialog(dialog)

    @classmethod
    def destroy_dialog(cls, dialog: QWidget) -> None:
        """Remove dialog and prepare for gc."""
        cls._list.remove(dialog)
        dialog.deleteLater()

    @classmethod
    def open(cls, widget: QWidget, *, modal: bool = True) -> None:
        """Show the dialog."""
        Dialogs.register(widget)
        if modal:
            widget.open()
        else:
            widget.show()
            try:
                widget.raise_()  # Mac ?? Wayland ??
            except Exception as ex:  # noqa: BLE001
                print_err(str(ex))
            if hasattr(widget, "requestActivate"):
                widget.requestActivate()


##% [Widget Impl] DialogWidget
##% ────────────────────────────────────────────────────────────────────────────
class DialogWidget(QDialog):
    """Simple Dialog with onClose as signal."""

    onClose = Signal(QCloseEvent)
    onLanguageChange = Signal()
    onResize = Signal(QResizeEvent)
    onMove = Signal(QMoveEvent)

    def __init__(self, *args: tuple, **kwargs: KwArgs) -> None:
        super().__init__(*args, **kwargs)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Forward closeEvent to onClose signal."""
        self.onClose.emit(event)
        super().closeEvent(event)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.onLanguageChange.emit()
        super().changeEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        self.onResize.emit(event)
        return super().resizeEvent(event)

    def moveEvent(self, event: QMoveEvent) -> None:
        self.onMove.emit(event)
        return super().moveEvent(event)

##% [Widget] Dialog
##% ────────────────────────────────────────────────────────────────────────────
@contextmanager
def Dialog(
    title: str | None = None,
    *,
    size: tuple[int, int] | None = None,
    show: bool = True,
    modal: bool = True,
    parent: QWidget = None,
    **kwargs: KwArgs,
) -> Generator[DialogWidget, Any, Any]:
    """
    Dialog context manager/widget.

    Example:
    ~:code:../examples/ui/widgets.py[Dialog]:~

    :param str title: window title, defaults to None
    :param tuple[int, int] size: dialog size, defaults to None
    :param bool show: show automatically, defaults to True
    :param bool modal: window modality, defaults to True
    :param QWidget parent: parent widget, defaults to None
    :param dict[str, Any] **kwargs: Qt properties
    :return QDialog: The Dialog
    """
    if parent is None:
        parent = find_active_window()

    w = DialogWidget(parent=parent)

    if title is not None:
        w.setWindowTitle(str(title))
    set_qt_attrs(w, **kwargs)

    build_context().reset()
    with build_context().stack(w):
        yield w
        if isinstance(size, (tuple, list)):
            w.resize(size[0], size[1])
        else:
            w.adjustSize()
        if show:
            Dialogs.open(w, modal=modal)


##% [Widget] Scroll
##% ────────────────────────────────────────────────────────────────────────────
@contextmanager
def Scroll(*, add: bool = True, **kwargs: KwArgs) -> Generator[QScrollArea, Any, Any]:
    """
    Scrollable area context manager/widget.

    Example:
    ~:code:../examples/ui/widgets.py[Scroll]:~

    :param bool add: add to context, defaults to True
    :param dict[str, Any] **kwargs: Qt properties
    :return QScrollArea: Scroll widget
    """
    w = QScrollArea()
    set_qt_attrs(w, **kwargs)
    if add:
        place_widget(w)
    with build_context().stack(w):
        yield w


##% [Widget] GroupBox
##% ────────────────────────────────────────────────────────────────────────────
@contextmanager
def GroupBox(
    title: str | None = None,
    *,
    add: bool = True,
    **kwargs: KwArgs,
) -> Generator[QGroupBox, Any, Any]:
    """
    GroupBox context manager/widget.

    Example:
    ~:code:../examples/ui/widgets.py[GroupBox]:~

    :param str title: Group title, defaults to None
    :param bool add: add to context, defaults to True
    :param bool add: add to context, defaults to True
    :param dict[str, Any] **kwargs: Qt properties
    :return QGroupBox: The group widget
    """
    w = QGroupBox()
    if title:
        w.setTitle(title)
    set_qt_attrs(w, **kwargs)
    if add:
        place_widget(w)
    with build_context().stack(w):
        yield w


##% [Widget] Container
##% ────────────────────────────────────────────────────────────────────────────
class ContainerWidget(QWidget):
    """Custom container widget."""

    onLanguageChange = Signal()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.LanguageChange:
            self.onLanguageChange.emit()
        super().changeEvent(event)


@contextmanager
def Container(
    *,
    add: bool = True,
    top: bool = False,
    q_widget: type[QWidget] | None = None,
    **kwargs: KwArgs,
) -> Generator[QWidget, Any, Any]:
    """
    Simple container context/widget.

    Example
    ~:code:../examples/ui/widgets.py[Scroll]:~

    :param bool add: add to context, defaults to True
    :param dict[str, Any] **kwargs: Qt properties
    :return QFrame: The container widget
    """
    w = ContainerWidget() if q_widget is None else q_widget()
    set_qt_attrs(w, **kwargs)

    ctx = build_context()
    top = top or ctx.is_empty()

    if top:
        ctx.reset()
    elif add:
        place_widget(w)

    with ctx.stack(w):
        yield w


##% [Layout tool] Stretch
##% ────────────────────────────────────────────────────────────────────────────
def Stretch(stretch: int = 0) -> None:
    """
    Add stretch factor to the current layout.

    :param int stretch: 0-100 stretch factor, defaults to 0
    """
    layout = build_context().current().layout()
    if layout:
        layout.addStretch(stretch)


##% [Layout tool] Spacing
##% ────────────────────────────────────────────────────────────────────────────
def Spacing(size: int) -> None:
    """
    Adds spacing ro the current layout.

    :param int size: spacing
    """
    layout = build_context().current().layout()
    if layout:
        layout.addSpacing(size)


##% [Widget] TabContainer
##% ────────────────────────────────────────────────────────────────────────────
@contextmanager
def TabContainer(
    *,
    stretch: int = 0,
    add: bool = True,
    **kwargs: KwArgs,
) -> Generator[QTabWidget, Any, Any]:
    """
    Tab Container context/widget

    Example:
    ~:code:../examples/ui/widgets.py[TabContainer]:~

    :param int stretch: stretch, defaults to 0
    :param bool add: add to the context, defaults to True
    :param dict[str, Any] **kwargs: Qt properties
    :return QTabWidget: The widget
    """
    w = QTabWidget()
    set_qt_attrs(w, **kwargs)
    if add:
        place_widget(w, stretch=stretch)
    with build_context().stack(w):
        yield w


##% [Widget] Tab
##% ────────────────────────────────────────────────────────────────────────────
@contextmanager
def Tab(
    title: str,
    *,
    icon: QIcon = None,
    add: bool = True,
    **kwargs: KwArgs,
) -> Generator[QWidget, Any, Any]:
    """
    Tab widget/context in a tab container

    Example:
    ~:code:../examples/ui/widgets.py[TabContainer]:~

    :param str title: Tab's title
    :param QIcon icon: Icon, defaults to None
    :param bool add: add to the context, defaults to True
    :param dict[str, Any] **kwargs: Qt properties
    :return QWidget: the widget
    """
    w = QWidget()
    set_qt_attrs(w, **kwargs)
    with build_context().stack(w):
        yield w
    if add:
        if icon:
            build_context().current().addTab(w, icon, title)
        else:
            build_context().current().addTab(w, title)


##% [Widget] Splitter
##% ────────────────────────────────────────────────────────────────────────────
@contextmanager
def Splitter(*, add: bool = True, **kwargs: KwArgs) -> Generator[QSplitter, Any, Any]:
    """
    Split context/container

    Example:
    ~:code:../examples/ui/widgets.py[Splitter]:~

    :param bool add: add to current context, defaults to True
    :param dict[str, Any] **kwargs: Qt properties
    :return QSplitter: The splitter widget
    """
    w = QSplitter()
    set_qt_attrs(w, **kwargs)
    if add:
        place_widget(w)
    with build_context().stack(w):
        yield w


##% [Layout] Col (Vertical Box)
##% ────────────────────────────────────────────────────────────────────────────
@contextmanager
def Col(*, add: bool = True, **kwargs: KwArgs) -> Generator[QWidget, Any, Any]:
    """
    Vertical context/layout

    Example:
    ~:code:../examples/ui/widgets.py[Col]:~

    :param bool add: add to current context, defaults to True
    :param dict[str, Any] **kwargs: Qt properties
    :return QWidget: A container widget with Vertical layout
    """
    yield from setup_layout(QVBoxLayout(), add=add, **kwargs)


##% [Layout] Row (Horizontal Box)
##% ────────────────────────────────────────────────────────────────────────────
@contextmanager
def Row(*, add: bool = True, **kwargs: KwArgs) -> Generator[QWidget, None, None]:
    """
    Horizontal context/layout

    Example:
    ~:code:../examples/ui/widgets.py[Row]:~

    :param bool add: add to current context, defaults to True
    :param dict[str, Any] **kwargs: Qt properties
    :return QWidget: A container widget with Horizontal layout
    """
    yield from setup_layout(QHBoxLayout(), add=add, **kwargs)


##% [Layout] Stack (Stacked Layout)
##% ────────────────────────────────────────────────────────────────────────────
@contextmanager
def Stack(*, add: bool = True, **kwargs: KwArgs) -> Generator[QWidget, Any, Any]:
    """
    Stacked context/layout

    Example:
    ~:code:../examples/ui/widgets.py[Stack]:~

    :param bool add: add to current context, defaults to True
    :param dict[str, Any] **kwargs: Qt properties
    :return QWidget: A container widget with Stacked layout
    """
    yield from setup_layout(QStackedLayout(), add=add, **kwargs)


##% [Widget Impl] HtmlWidget
##% ────────────────────────────────────────────────────────────────────────────
class HtmlWidget(QLabel):
    """Html template widget."""

    VAR_RE = re.compile(r"\{\{(.*?)\}\}")  # template var: {{name}}
    base_path: Path
    css: str

    def __init__(self, base_path: Path, css: str) -> None:
        super().__init__()
        self.css = css or ""
        self.base_path = base_path

    def interpolator(self, variables: dict[str, Any]) -> Callable[[re.Match], str]:
        """Create a variable interpolator."""
        if variables:

            def replacer(match: re.Match) -> str:
                var_name = match.group(1)
                if var_name == "__base__":
                    return str(self.base_path)
                return str(variables.get(var_name, ""))

        else:

            def replacer(match: re.Match) -> str:
                if match.group(1) == "__base__":
                    return str(self.base_path)
                return ""

        return replacer

    def setValue(self, html: str, variables: dict[str, Any] | None = None) -> None:
        """Set content and apply interpolations."""
        content = HtmlWidget.VAR_RE.sub(self.interpolator(variables), html)
        self.setText(f"<style>{self.css}</style>{content}")


##% [Widget] Html
##% ────────────────────────────────────────────────────────────────────────────
def Html(
    *,
    html: str | None = None,
    file: str | None = None,
    css: str | None = None,
    css_file: str | None = None,
    base_path: str | None = None,
    background: str | None = None,
    stretch: int = 0,
    alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
    variables: dict[str, Any] | None = None,
    add: bool = True,
    **kwargs: KwArgs,
) -> HtmlWidget:
    """
    Basic HTML Render widget.

    Example:
    ~:code:../examples/ui/widgets.py[Html]:~

    :param str html: raw html content, defaults to None
    :param str file: path to html file, defaults to None
    :param str css: raw css code, defaults to None
    :param str css_file: path to css file, defaults to None
    :param str base_path: base dir for loading resources, defaults to None
    :param str background: background color code, defaults to None
    :param int stretch: layout stretch, defaults to 0
    :param Qt.Alignment alignment: layout alignment, defaults to Qt.Alignment()
    :param dict[str, Any] variables: interpolation variables, defaults to None
    :param bool add: add to current context, defaults to True
    :param dict[str, Any] **kwargs: Qt properties of QLabel
    :return HtmlWidget: Html Widget
    """
    if html and file:
        msg = "html and file arguments are mutually exclusive"
        raise ValueError(msg)

    if base_path:
        base_path = Path(base_path)
        if file:
            file = Path(base_path, file)
        if css_file:
            css_file = Path(base_path, css_file)
    elif file:
        base_path = Path(file).parent
        if css_file:
            css_file = Path(base_path, css_file)

    if html is None:
        with open(file) as f:
            html = f.read()

    base_css = ""
    if css_file:
        with open(css_file) as f:
            base_css = f.read()

    if css is not None:
        base_css += css

    label = HtmlWidget(base_path, base_css)
    label.setValue(html, variables)

    if background is not None:
        label.setStyleSheet(f"background-color: {background};")

    set_qt_attrs(label, **kwargs)
    if add:
        place_widget(label, stretch=stretch, alignment=alignment)
    return label


##% [Widget] TextLabel
##% ────────────────────────────────────────────────────────────────────────────
def TextLabel(
    text: str = "",
    *,
    stretch: int = 0,
    alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
    add: bool = True,
    **kwargs: KwArgs,
) -> QLabel:
    """
    Simple text label widget.

    Example:
    ~:code:../examples/ui/widgets.py[TextLabel]:~

    :param str text: text, defaults to ""
    :param int stretch: layout stretch, defaults to 0
    :param Qt.Alignment alignment: layout alignment, defaults to Qt.Alignment()
    :param bool add: add to current context, defaults to True
    :param dict[str, Any] **kwargs: Qt properties of QLabel
    :return QLabel: The widget
    """
    label = QLabel(text)
    set_qt_attrs(label, **kwargs)
    if add:
        place_widget(label, stretch=stretch, alignment=alignment)
    return label


##% [Widget] IconLabel
##% ────────────────────────────────────────────────────────────────────────────
def IconLabel(
    icon: str | QIcon | None = None,
    *,
    size: tuple[int, int] = (16, 16),
    stretch: int = 0,
    alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
    add: bool = True,
    **kwargs: KwArgs,
) -> QLabel:
    """
    Simple icon label widget.

    Example:
    ~:code:../examples/ui/widgets.py[IconLabel]:~

    :param str icon: icon name or QIcon, defaults to None
    :param int stretch: layout stretch, defaults to 0
    :param Qt.Alignment alignment: layout alignment, defaults to Qt.Alignment()
    :param bool add: add to current context, defaults to True
    :param dict[str, Any] **kwargs: Qt properties of QLabel
    :return QLabel: The widget
    """
    label = QLabel()
    if isinstance(icon, str):
        icon = QIcon.fromTheme(icon)
    if isinstance(icon, QIcon):
        label.setPixmap(icon.pixmap(*size))

    label.setEnabled(False)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.MinimumExpanding)
    label.setAutoFillBackground(True)
    label.setMinimumSize(*size)

    set_qt_attrs(label, **kwargs)
    if add:
        place_widget(label, stretch=stretch, alignment=alignment)
    return label


##% [Widget] InputFloat
##% ────────────────────────────────────────────────────────────────────────────
def InputFloat(
    value: float = 0.0,
    *,
    name: str | None = None,
    min: float = 0.0,
    max: float = sys.float_info.max,
    decimals: int = 6,
    step: float = 0.01,
    label: QWidget | str | None = None,
    stretch: int = 0,
    alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
    add: bool = True,
    **kwargs: KwArgs,
) -> QDoubleSpinBox:
    """
    Input float widget.

    Example:
    ~:code:../examples/ui/widgets.py[InputFloat]:~

    :param float value: initial value, defaults to 0.0
    :param str name: objectName, defaults to None
    :param float min: minimum accepted value, defaults to 0.0
    :param float max: maximum accepted value, defaults to sys.float_info.max
    :param int decimals: decimal digits, defaults to 6
    :param float step: spin steps, defaults to 0.01
    :param Union[QWidget, str] label: ui label, defaults to None
    :param int stretch: layout stretch, defaults to 0
    :param Qt.Alignment alignment: layout alignment, defaults to Qt.Alignment()
    :param bool add: add to current context, defaults to True
    :param dict[str, Any] **kwargs: Qt properties
    :return QDoubleSpinBox: The input widget
    """
    widget = QDoubleSpinBox()
    widget.setMinimum(min)
    widget.setMaximum(max)
    widget.setSingleStep(step)
    widget.setDecimals(decimals)
    widget.setValue(value)
    set_qt_attrs(widget, **kwargs)
    if name:
        widget.setObjectName(name)
    if add:
        place_widget(widget, label=label, stretch=stretch, alignment=alignment)
    return widget


##% [Widget Impl] InputTextWidget
##% ────────────────────────────────────────────────────────────────────────────
class InputTextWidget(QLineEdit):
    """Basic input text widget."""

    def __init__(self, *args: tuple, **kwargs: KwArgs) -> None:
        super().__init__(*args, **kwargs)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def value(self) -> str:
        """Return text content."""
        return self.text()

    def setValue(self, value: Any) -> None:
        """Set text content."""
        self.setText(str(value))


##% [Widget Impl] InputTextMultilineWidget
##% ────────────────────────────────────────────────────────────────────────────
class InputTextMultilineWidget(QTextEdit):
    """Multiline input text widget."""

    def __init__(self, max_length: int = 0, *args: tuple, **kwargs: KwArgs) -> None:
        super().__init__(*args, **kwargs)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.max_length = max_length
        if max_length > 0:
            self.textChanged.connect(self._check_length)

    def _check_length(self) -> None:
        """Check length and truncate if needed."""
        text = self.toPlainText()
        if len(text) > self.max_length:
            self.setPlainText(text[: self.max_length])
            self.moveCursor(QTextCursor.MoveOperation.End)

    def value(self) -> str:
        """Return text content."""
        return self.toPlainText()

    def setValue(self, value: Any) -> None:
        """Set text content."""
        self.setPlainText(str(value))


##% [Widget] InputText
##% ────────────────────────────────────────────────────────────────────────────
def InputText(
    value: str = "",
    *,
    name: str | None = None,
    label: QWidget | str = None,
    stretch: int = 0,
    alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
    add: bool = True,
    **kwargs: KwArgs,
) -> InputTextWidget:
    """
    Input text widget.

    Example:
    ~:code:../examples/ui/widgets.py[InputText]:~

    :param str value: initial value, defaults to ""
    :param str name: objectName, defaults to None
    :param Union[QWidget, str] label: gui label, defaults to None
    :param int stretch: layout stretch, defaults to 0
    :param Qt.Alignment alignment: layout alignment, defaults to Qt.Alignment()
    :param bool add: add to current context, defaults to True
    :param dict[str, Any] **kwargs: Qt properties
    :return InputTextWidget: The widget
    """
    widget = InputTextWidget()
    widget.setText(value)
    set_qt_attrs(widget, **kwargs)
    if name:
        widget.setObjectName(name)
    if add:
        place_widget(widget, label=label, stretch=stretch, alignment=alignment)
    return widget


##% [Widget] InputTextMultiline
##% ────────────────────────────────────────────────────────────────────────────
def InputTextMultiline(
    value: str = "",
    *,
    name: str | None = None,
    label: QWidget | str = None,
    stretch: int = 0,
    alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
    max_length: int = 0,
    add: bool = True,
    **kwargs: KwArgs,
) -> InputTextMultilineWidget:
    """
    Input text widget (multiline).

    Example:
    ~:code:../examples/ui/widgets.py[InputText]:~

    :param str value: initial value, defaults to ""
    :param str name: objectName, defaults to None
    :param Union[QWidget, str] label: gui label, defaults to None
    :param int stretch: layout stretch, defaults to 0
    :param Qt.Alignment alignment: layout alignment, defaults to Qt.Alignment()
    :param bool add: add to current context, defaults to True
    :param dict[str, Any] **kwargs: Qt properties
    :return InputTextMultilineWidget: The widget
    """
    widget = InputTextMultilineWidget(max_length=max_length)
    widget.setValue(value)
    set_qt_attrs(widget, **kwargs)
    if name:
        widget.setObjectName(name)
    if add:
        place_widget(widget, label=label, stretch=stretch, alignment=alignment)
    return widget


##% [Widget Impl] LabelEx
##% ────────────────────────────────────────────────────────────────────────────
class LabelEx(QWidget):
    """QLable with icon."""

    ICON_SIZE = 16

    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setLayout(QHBoxLayout(self))
        self.setContentsMargins(0, 0, 0, 0)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(*args, **kwargs)
        self.icon = QLabel(self)
        self.icon.setVisible(False)
        self.icon.setMaximumWidth(LabelEx.ICON_SIZE)
        self.layout().addWidget(self.icon)
        self.layout().addWidget(self.label)

    def setText(self, text: str) -> None:
        self.label.setText(str(text))

    def text(self) -> str:
        return self.label.text()

    def setNotification(self, icon: str | QIcon, text: str | None = None) -> None:
        self.icon.setToolTip(text or "")
        size = QSize(LabelEx.ICON_SIZE, LabelEx.ICON_SIZE)
        if isinstance(icon, str):
            icon = QIcon.fromTheme(icon)
        self.icon.setPixmap(icon.pixmap(size))
        self.icon.setVisible(True)

    def clearNotification(self) -> None:
        self.icon.setVisible(False)


##% [Widget Impl] InputQuantityWidget
##% ────────────────────────────────────────────────────────────────────────────
class InputQuantityWidget(QWidget):
    """Input quantity widget."""

    valueChanged = Signal(object)

    def __init__(self, editor: QWidget) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setLayout(QVBoxLayout(self))
        self.setContentsMargins(0, 0, 0, 0)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(editor)
        self.editor = editor
        editor.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        if hasattr(editor, "valueChanged"):
            editor.valueChanged.connect(lambda v: self.valueChanged.emit(v))
        elif hasattr(editor, "textChanged"):
            editor.textChanged.connect(lambda v: self.valueChanged.emit(v))

    def value(self) -> Any:
        return self.editor.property("rawValue")

    def quantity(self) -> Any:
        return self.editor.property("value")

    def rawValue(self) -> Any:
        return self.editor.property("rawValue")

    def setValue(self, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, App.Units.Quantity):
            self.editor.setProperty("value", value)
        elif hasattr(self.editor, "setValue"):
            self.editor.setValue(value)
        elif hasattr(self.editor, "setText"):
            self.editor.setText(str(value))

    def setMinimum(self, value: float) -> None:
        return self.editor.setProperty("minimum", value)

    def setMaximum(self, value: float) -> None:
        return self.editor.setProperty("maximum", value)

    def setSingleStep(self, value: float) -> None:
        return self.editor.setProperty("singleStep", value)

    def setUnit(self, value: str) -> None:
        return self.editor.setProperty("unit", value)

    def setToolTip(self, tip: str) -> None:
        self.editor.setToolTip(tip)

    # def moveEvent(self, event: QMoveEvent) -> None:
    #     super().moveEvent(event)
    #     self.fixValidationIconSize()

    # def resizeEvent(self, event: QResizeEvent) -> None:
    #     super().resizeEvent(event)
    #     self.fixValidationIconSize()

    # def fixValidationIconSize(self) -> None:
    #     # Fix nasty huge validation icon
    #     if isinstance(icon := self.editor.findChild(QLabel), QLabel):
    #         icon.setScaledContents(True)
    #         size = self.frameSize()
    #         h = size.height() - 8
    #         left = size.width() - h - 4
    #         icon.setStyleSheet(f"""QLabel {{
    #                                border: none;
    #                                padding: 0px;
    #                                max-width: {h}px;
    #                                max-height:{h}px;
    #                                min-width: {h}px;
    #                                min-height:{h}px;
    #                                }}
    #                                """)
    #         icon.move(left, 4)
    #         icon.update()

    def setFocus(self) -> None:
        """Set focus to the editor."""
        self.editor.setFocus()


##% [Widget] InputQuantity
##% ────────────────────────────────────────────────────────────────────────────


class PropertyAccessorAdapter(Protocol):
    """
    Protocol for adapting property access on FreeCAD DocumentObjects.

    This adapter defines a standard interface for getting and setting properties
    on FreeCAD DocumentObject instances, allowing for flexible property access
    strategies.
    """

    def get(self, obj: DocumentObject, prop: str) -> Any: ...
    def set(self, obj: DocumentObject, prop: str, value: Any) -> None: ...


class InputPropertyWrapper(QObject):
    """
    A wrapper class that connects a FreeCAD property to a UI input widget.

    Enabling two-way data binding and automatic updates.
    This class binds a property of a FreeCAD DocumentObject to an InputQuantityWidget,
    synchronizing changes between the UI and the underlying object property.
    It supports optional accessor adapters for custom get/set logic and handles
    automatic recomputation of the object and any dependent VarSet objects when
    the property value changes.
    """

    def __init__(
        self,
        parent: InputQuantityWidget,
        *,
        obj: DocumentObject,
        property: str,
        auto_apply: bool,
        accessor_adapter: PropertyAccessorAdapter | None = None,
    ) -> None:
        super().__init__(parent)

        ee = Gui.ExpressionBinding(parent.editor)
        ee.bind(obj, property)
        ee.setAutoApply(auto_apply)
        self.ee = ee

        self.accessor_adapter = accessor_adapter
        if accessor_adapter:
            getter, setter = accessor_adapter.get, accessor_adapter.set
        else:
            getter, setter = getattr, setattr

        value = getter(obj, property)
        parent.setValue(value)

        def on_value_changed(v: Any) -> None:
            setter(obj, property, v)
            obj.recompute()
            for ref in obj.InListRecursive:
                if ref.isDerivedFrom("App::VarSet"):
                    ref.recompute()

        parent.valueChanged.connect(on_value_changed)



def InputQuantity(
    value: Numeric = None,
    *,
    name: str | None = None,
    min: Numeric = None,
    max: Numeric = None,
    step: Numeric = 1.0,
    label: QWidget | str = None,
    stretch: int = 0,
    alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
    unit: str | None = None,
    obj: DocumentObject | None = None,
    property: str | None = None,
    auto_apply: bool = True,
    add: bool = True,
    widget_type: str = "Gui::InputField",
    accessor_adapter: PropertyAccessorAdapter | None = None,
    **kwargs: KwArgs,
) -> InputQuantityWidget:
    """
    Input Quantity Widget with unit and expressions support.

    Example:
    ~:code:../examples/ui/widgets.py[InputQuantity]:~

    :param Numeric value: Initial value, defaults to None
    :param str name: objectName (Qt), defaults to None
    :param Numeric min: Minimum accepted value, defaults to None
    :param Numeric max: Maximum accepted value, defaults to None
    :param Numeric step: Spin step, defaults to 1.0
    :param Union[QWidget, str] label: gui label, defaults to None
    :param int stretch: Layout stretch, defaults to 0
    :param Qt.Alignment alignment: Layout alignment, defaults to Qt.Alignment()
    :param str unit: quantity unit (i.e. mm, in, ...), defaults to None
    :param DocumentObject obj: Object to bind the expression engine, defaults to None
    :param str property: Property name of the bounded DocumentObject if any, defaults to None
    :param bool add: Add to current context, defaults to True
    :param dict[str, Any] **kwargs: Qt properties
    :return InputQuantityWidget: The widget
    """
    if obj and property and property not in obj.PropertiesList:
        msg = f"Invalid property name: {property}"
        raise ValueError(msg)

    editor: QWidget = _fc_ui_loader.createWidget(widget_type)
    widget = InputQuantityWidget(editor)
    if min is not None:
        widget.setMinimum(min)
    if max is not None:
        widget.setMaximum(max)
    if step is not None:
        widget.setSingleStep(step)
    if unit is not None:
        widget.setUnit(unit)
    set_qt_attrs(editor, **kwargs)

    if name:
        widget.setObjectName(name)

    if obj and property:
        widget.InputPropertyWrapper = InputPropertyWrapper(
            widget,
            obj=obj,
            property=property,
            auto_apply=auto_apply,
            accessor_adapter=accessor_adapter,
        )
    elif value is not None:
        widget.setValue(value)

    if add:
        place_widget(widget, label=label, stretch=stretch, alignment=alignment)

    return widget


##% [Widget] InputInt
##% ────────────────────────────────────────────────────────────────────────────
def InputInt(
    value: int = 0,
    *,
    name: str | None = None,
    min: int = 0,
    max: int | None = None,
    step: int = 1,
    label: QWidget | str = None,
    stretch: int = 0,
    alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
    add: bool = True,
    **kwargs: KwArgs,
) -> QSpinBox:
    """
    Input int widget.

    Example:
    ~:code:../examples/ui/widgets.py[InputInt]:~

    :param int value: initial value, defaults to 0
    :param str name: objectName, defaults to None
    :param int min: minimum accepted value, defaults to 0
    :param int max: maximum accepted value, defaults to None
    :param int step: spin steps, defaults to 1
    :param Union[QWidget, str] label: ui label, defaults to None
    :param int stretch: layout stretch, defaults to 0
    :param Qt.Alignment alignment: layout alignment, defaults to Qt.Alignment()
    :param bool add: add to current context, defaults to True
    :param dict[str, Any] **kwargs: Qt properties
    :return QSpinBox: The input widget
    """
    widget = QSpinBox()
    widget.setMinimum(min)
    if max is not None:
        widget.setMaximum(max)
    widget.setSingleStep(step)
    widget.setValue(value)
    set_qt_attrs(widget, **kwargs)
    if name:
        widget.setObjectName(name)
    if add:
        place_widget(widget, label=label, stretch=stretch, alignment=alignment)
    return widget


##% [Widget Impl] QCheckBoxExt
##% ────────────────────────────────────────────────────────────────────────────
class QCheckBoxExt(QCheckBox):
    """Basic boolean input based on checkbox."""

    def __init__(self, *args: tuple, **kwargs: KwArgs) -> None:
        super().__init__(*args, **kwargs)

    def value(self) -> bool:
        """Return the value."""
        return self.checkState() == Qt.Checked

    def setValue(self, value: bool) -> None:  # noqa: FBT001
        """Set the value."""
        self.setCheckState(Qt.Checked if value else Qt.Unchecked)


##% [Widget] InputBoolean
##% ────────────────────────────────────────────────────────────────────────────
def InputBoolean(
    value: bool = False,  # noqa: FBT001, FBT002
    *,
    name: str | None = None,
    label: QWidget | str = None,
    stretch: int = 0,
    alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
    add: bool = True,
    **kwargs: KwArgs,
) -> QCheckBoxExt:
    """
    Input boolean widget as QCheckBox.

    Example:
    ~:code:../examples/ui/widgets.py[InputBoolean]:~

    :param bool value: initial value, defaults to False
    :param str name: objectName, defaults to None
    :param Union[QWidget, str] label: ui label, defaults to None
    :param int stretch: layout stretch, defaults to 0
    :param Qt.Alignment alignment: layout alignment, defaults to Qt.Alignment()
    :param bool add: add to the gui, defaults to True
    :param dict[str, Any] **kwargs: settable QCheckBox properties
    :return QCheckBoxExt: The widget
    """
    widget = QCheckBoxExt()
    widget.setValue(value)
    set_qt_attrs(widget, **kwargs)
    if name:
        widget.setObjectName(name)
    if add:
        place_widget(widget, label=label, stretch=stretch, alignment=alignment)
    return widget


##% [Layout] LayoutWidget
##% ────────────────────────────────────────────────────────────────────────────
class LayoutWidget(QWidget):
    """Layout widget builder."""

    def __init__(self, layout_builder: Callable[[], QLayout], **kwargs: KwArgs) -> None:
        super().__init__()
        layout = layout_builder()
        set_qt_attrs(layout, **kwargs)
        self.setLayout(layout)

    def addWidget(
        self,
        widget: QWidget,
        stretch: int = 0,
        alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
    ) -> None:
        self.layout().addWidget(widget, stretch, alignment)

    def addStretch(self, stretch: int = 0) -> None:
        self.layout().addStretch(stretch)

    def addSpacing(self, size: int) -> None:
        self.layout().addSpacing(size)


##% [Widget Impl] InputFloatListWidget
##% ────────────────────────────────────────────────────────────────────────────
class InputFloatListWidget(QWidget):
    """Input widget for float lists."""

    valueChanged = Signal()

    def __init__(
        self,
        *,
        count: int = 0,
        values: list[float] | None = None,
        label_fn: Callable[[int], str] | None = None,
        resizable: bool = False,
        min_count: int = 0,
        **kwargs: KwArgs,
    ) -> None:
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self.options = kwargs
        self.min_count = min_count

        if not values:
            values = [0.0] * count
        else:
            count = len(values)

        if count < min_count:
            msg = f"Minimum rows required are {min_count}"
            raise ValueError(msg)

        if not label_fn:
            label_fn = str

        self._label_fn = label_fn

        self.inputs = []
        labels = tuple(QLabel(label_fn(i)) for i in range(count))
        for i in range(count):
            ctrl = InputFloat(value=values[i], add=False, **kwargs)
            ctrl.valueChanged.connect(self.valueChanged)
            self.inputs.append(ctrl)

        panel = LayoutWidget(QVBoxLayout, contentsMargins=(0, 0, 0, 0))
        layout.addWidget(panel)
        for i in range(count):
            panel.addWidget(widget_with_label_row(self.inputs[i], labels[i]))
        self.panel = panel

        if resizable:
            self.resize_controls()

    def resize_controls(self) -> None:
        buttons = LayoutWidget(QHBoxLayout, contentsMargins=(0, 0, 0, 0))
        self.layout().addWidget(buttons, 0, alignment=Qt.AlignRight)

        @button(label="+", add=False, tool=True)
        def add() -> None:
            self.addValue(**self.options)

        @button(label="−", add=False, tool=True)  # noqa: RUF001
        def remove() -> None:
            self.removeLast()

        buttons.addWidget(add, alignment=Qt.AlignRight)
        buttons.addWidget(remove, alignment=Qt.AlignRight)

    def value(self) -> tuple[float, ...]:
        return tuple(i.value() for i in self.inputs)

    def setValue(self, value: list[float] | tuple[float, ...]) -> None:
        while len(value) > len(self.inputs):
            self.addValue()
        while len(value) < len(self.inputs):
            self.removeLast()
        for i, w in enumerate(self.inputs):
            w.setValue(value[i])

    def addValue(self, **kwargs: KwArgs) -> None:
        input_ = InputFloat(add=False, **kwargs)
        input_.valueChanged.connect(self.valueChanged)
        i = len(self.inputs)
        self.inputs.append(input_)
        self.panel.addWidget(widget_with_label_row(input_, self._label_fn(i)))

    def removeLast(self) -> None:
        if len(self.inputs) > self.min_count:
            item = self.inputs.pop()
            item.parent().setParent(None)


##% [Widget] InputFloatList
##% ────────────────────────────────────────────────────────────────────────────
def InputFloatList(
    values: list[float] | None = None,
    label: QWidget | str | None = None,
    *,
    name: str | None = None,
    label_fn: Callable[[int], str] | None = None,
    count: int = 0,
    resizable: bool = False,
    min_count: int = 0,
    add: bool = True,
    **kwargs: KwArgs,
) -> InputFloatListWidget:
    """
    Widget to accept lists of float numbers.

    Example:
    ~:code:../examples/ui/widgets.py[InputFloatList]:~

    :param list[float] values: initial values, defaults to None
    :param Union[QWidget, str] label: ui label, defaults to None
    :param str name: objectName, defaults to None
    :param Callable[[int], str] label_fn: label provider (for custom row labels), defaults to None
    :param int count: number of autogenerated rows, defaults to 0
    :param bool resizable: allow resizing the list, defaults to False
    :param int min_count: minimum number of rows, defaults to 0
    :param bool add: add to the gui, defaults to True
    :param dict[str, Any] **kwargs: Qt properties
    :return InputFloatListWidget: The widget
    """
    widget = InputFloatListWidget(
        count=count,
        label_fn=label_fn,
        values=values,
        resizable=resizable,
        min_count=min_count,
        **kwargs,
    )
    if name:
        widget.setName(name)
    if add:
        place_widget(widget, label=label)
    return widget


##% [Widget Impl] InputVectorWrapper
##% ────────────────────────────────────────────────────────────────────────────
class InputVectorWrapper:
    """Basic vector input."""

    def __init__(self, g: QWidget, x: QDoubleSpinBox, y: QDoubleSpinBox, z: QDoubleSpinBox) -> None:
        self.group = g
        self.x = x
        self.y = y
        self.z = z

    def value(self) -> Vector:
        return Vector(self.x.value(), self.y.value(), self.z.value())

    def setValue(self, value: Any) -> None:
        v = to_vec(value)
        self.x.setValue(v.x)
        self.y.setValue(v.y)
        self.z.setValue(v.z)


##% [Widget] InputVector
##% ────────────────────────────────────────────────────────────────────────────
def InputVector(
    label: QWidget | str | None = None,
    value: tuple | Vector = (0.0, 0.0, 0.0),
) -> InputVectorWrapper:
    """
    Widget to accept a vector.

    Example:
    ~:code:../examples/ui/widgets.py[InputVector]:~

    :param Union[QWidget, str] label: ui label, defaults to None
    :param Union[tuple, Vector] value: vector value, defaults to (0.0, 0.0, 0.0)
    :return InputVectorWrapper: The widget
    """
    with GroupBox(title=label) as g:
        with Col():
            x = InputFloat(label="X:")
            y = InputFloat(label="Y:")
            z = InputFloat(label="Z:")
            widget = InputVectorWrapper(g, x, y, z)
            widget.setValue(value)
            return widget


##% [Widget Impl] InputOptionsWidget
##% ────────────────────────────────────────────────────────────────────────────
class InputOptionsWidget(QComboBox):
    """Basic ComboBox input to select from options."""

    class SelectAllLineEdit(QLineEdit):
        def focusInEvent(self, event: QEvent) -> None:
            super().focusInEvent(event)
            self.selectAll()

    def __init__(self, data: dict[str, Hashable], selectOnFocus: bool) -> None:
        super().__init__()
        for label, value in data.items():
            self.addItem(str(label), value)
        if selectOnFocus:
            self.setLineEdit(InputOptionsWidget.SelectAllLineEdit(self))

    def addOption(self, label: str, value: Hashable) -> None:
        self.addItem(str(label), value)

    def setOptions(self, data: dict[str, Hashable]) -> None:
        self.clear()
        for label, value in data.items():
            self.addItem(str(label), value)

    def removeOption(self, value: Hashable) -> None:
        index = self.findData(value)
        if index == -1:
            return
        self.removeItem(index)

    def values(self) -> Iterator[Hashable]:
        for i in range(self.count()):
            yield self.itemData(i)

    def value(self) -> Hashable:
        return self.currentData()

    def setValue(self, value: Hashable) -> None:
        self.setCurrentIndex(self.findData(value))


##% [Widget] InputOptions
##% ────────────────────────────────────────────────────────────────────────────
def InputOptions(
    options: dict[str, Hashable],
    value: Hashable = None,
    label: str | None = None,
    *,
    name: str | None = None,
    stretch: int = 0,
    alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
    add: bool = True,
    select_on_focus: bool = False,
    **kwargs: KwArgs,
) -> InputOptionsWidget:
    """
    ComboBox widget.

    Example:
    ~:code:../examples/ui/widgets.py[InputOptions]:~

    :param dict[str, Hashable] options: label to value mapping
    :param Hashable value: initial value, defaults to None
    :param str label: gui label, defaults to None
    :param str name: objectName, defaults to None
    :param int stretch: layout stretch, defaults to 0
    :param Qt.Alignment alignment: layout alignment, defaults to Qt.Alignment()
    :param dict[str, Any] **kwargs: Qt properties
    :return InputOptionsWidget: The widget
    """
    widget = InputOptionsWidget(options, selectOnFocus=select_on_focus)
    set_qt_attrs(widget, **kwargs)
    if value is not None:
        widget.setValue(value)
    if name:
        widget.setObjectName(name)
    if add:
        place_widget(widget, label=label, stretch=stretch, alignment=alignment)
    return widget


##% [Widget] InputSelectOne
##% ────────────────────────────────────────────────────────────────────────────
class InputSelectOne:
    """3D Selection widget. Allows to pick an object."""

    def __init__(
        self,
        label: str | None = None,
        *,
        name: str | None = None,
        active: bool = False,
        auto_deactivate: bool = True,
    ) -> None:
        """
        3D Selection widget. Allows to pick an object.

        Example:
        ~:code:../examples/ui/widgets.py[InputSelectOne]:~

        :param str label: gui label, defaults to None
        :param str name: objectName, defaults to None
        :param bool active: activated by default, defaults to False
        :param bool auto_deactivate: _description_, defaults to True
        """
        self._value = None
        self._pre = None
        self._auto_deactivate = auto_deactivate
        self.selected = PySignal()
        with Row(
            add=False,
            spacing=0,
            margin=0,
            contentsMargins=(0, 0, 0, 0),
        ) as ctl:

            @button(
                text=_tr_select,
                tool=True,
                checkable=True,
                styleSheet="QToolButton:checked{background-color: #FF0000; color:#FFFFFF;}",
                focusPolicy=Qt.FocusPolicy.NoFocus,
                objectName=name,
                checked=active,
            )
            def select() -> None:
                pass

            @button(
                tool=True,
                focusPolicy=Qt.FocusPolicy.NoFocus,
                icon=QIcon(":icons/edit-cleartext.svg"),
            )
            def clear() -> None:
                self.setValue(None)

            display = QLineEdit()
            display.setReadOnly(True)
            place_widget(display)

            self.display = display
            self.button = select
            register_select_observer(select, self)

            with Parent():
                place_widget(ctl, label=label)

    @property
    def active(self) -> bool:
        return self.button.isChecked()

    def value(self) -> SelectedObject | None:
        return self._value

    def pre(self) -> SelectedObject | None:
        return self._pre

    def setValue(self, value: SelectedObject | None) -> None:
        self._value = value
        if value:
            self.display.setText(f"{value.doc}#{value.obj}.{value.sub}")
            if self._auto_deactivate:
                self.button.setChecked(False)
            self.selected.emit(self._value)
        else:
            self.display.setText("")

    def setPreselection(self, doc: str, obj: str, sub: str) -> None:
        if self.button.isChecked():
            self._pre = SelectedObject(doc, obj, sub)

    def addSelection(self, doc: str, obj: str, sub: str, pnt: Vector) -> None:
        if self.button.isChecked():
            self.setValue(SelectedObject(doc, obj, sub, pnt))

    def removeSelection(self, doc: str, obj: str, _sub: str) -> None:
        if self.button.isChecked() and self._value:
            v = self._value
            if (v.doc, v.obj) == (doc, obj):
                self.setValue(None)

    def setSelection(self, doc: str) -> None:
        if self.button.isChecked():
            self.setValue(SelectedObject(doc, Gui.Selection.getSelection()[-1].Name))

    def clearSelection(self, doc: str) -> None:
        pass


##% [Widget] InputSelectMany
##% ────────────────────────────────────────────────────────────────────────────
class InputSelectMany:
    """Simple widget to get multiple object selection."""

    ValueDataRole = Qt.UserRole

    def __init__(
        self,
        label: str | None = None,
        *,
        name: str | None = None,
        active: bool = False,
    ) -> None:
        """
        3D Multi-Selection Widget.

        Example:
        ~:code:../examples/ui/widgets.py[InputSelectMany]:~

        :param str label: gui label, defaults to None
        :param str name: objectName, defaults to None
        :param bool active: active by default or not, defaults to False
        """
        self._value = set()
        self.selected = PySignal()
        with Col(add=False, spacing=0, margin=0, contentsMargins=(0, 0, 0, 0)) as ctl:
            with Row(spacing=0, margin=0, contentsMargins=(0, 0, 0, 0)):

                @button(
                    text=_tr_add,
                    alignment=Qt.AlignLeft,
                    tool=True,
                    checkable=True,
                    styleSheet="QToolButton:checked{background-color: #FF0000; color:#FFFFFF;}",
                    focusPolicy=Qt.FocusPolicy.NoFocus,
                    objectName=name,
                    checked=active,
                )
                def select() -> None:
                    pass

                @button(
                    text=_tr_remove,
                    tool=True,
                    alignment=Qt.AlignLeft,
                    focusPolicy=Qt.FocusPolicy.NoFocus,
                )
                def remove() -> None:
                    selected = self.display.selectedItems()
                    for item in selected:
                        value = item.data(0, InputSelectMany.ValueDataRole)
                        self._value.remove(value)
                        self.display.takeTopLevelItem(self.display.indexOfTopLevelItem(item))

                @button(
                    text=_tr_clean,
                    tool=True,
                    alignment=Qt.AlignLeft,
                    focusPolicy=Qt.FocusPolicy.NoFocus,
                    icon=QIcon(":icons/edit-cleartext.svg"),
                )
                def clear() -> None:
                    self._value.clear()
                    self.display.clear()

                Stretch()

            display = QTreeWidget()
            display.setColumnCount(2)
            display.setHeaderLabels([_tr_object, _tr_sub_object])
            place_widget(display)

            self.display = display
            self.button = select
            register_select_observer(select, self)

            with Parent():
                with GroupBox(title=label):
                    place_widget(ctl)

    @property
    def active(self) -> bool:
        return self.button.isChecked()

    def value(self) -> list[SelectedObject]:
        return self._value

    def addValue(self, value: SelectedObject) -> None:
        if value not in self._value:
            item = QTreeWidgetItem([value.obj, value.sub])
            item.setData(0, InputSelectMany.ValueDataRole, value)
            self.display.addTopLevelItem(item)
            self._value.add(value)
            self.selected.emit(value)

    def setPreselection(self, doc: str, obj: str, sub: str) -> None:
        pass

    def addSelection(self, doc: str, obj: str, sub: str, pnt: Vector) -> None:
        if self.button.isChecked():
            self.addValue(SelectedObject(doc, obj, sub, pnt))

    def removeSelection(self, doc: str, obj: str, sub: str) -> None:
        pass

    def setSelection(self, doc: str) -> None:
        if self.button.isChecked():
            self.addValue(SelectedObject(doc, Gui.Selection.getSelection()[-1].Name))

    def clearSelection(self, doc: str) -> None:
        pass


##% [Widget] button
##@ [Decorator] button
##% ────────────────────────────────────────────────────────────────────────────
def button(
    label: str | None = None,
    *,
    tool: bool = False,
    icon: QIcon | str | None = None,
    stretch: int = 0,
    alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
    add: bool = True,
    **kwargs: KwArgs,
) -> Callable[[Callable[[], None]], QAbstractButton]:
    """
    Button Widget.

    Example:
    ~:code:../examples/ui/widgets.py[buttons]:~

    :param str label: text of the button, defaults to None
    :param bool tool: use tool style button, defaults to False
    :param Union[QIcon, str] icon: icon, defaults to None
    :param int stretch: layout stretch, defaults to 0
    :param Qt.Alignment alignment: layout alignment, defaults to Qt.Alignment()
    :param bool add: add to current context, defaults to True
    :return QAbstractButton: The widget
    """

    def wrapper(handler: Callable[[], None]) -> QAbstractButton:
        return Button(
            label=label,
            clicked=handler,
            tool=tool,
            icon=icon,
            stretch=stretch,
            alignment=alignment,
            add=add,
            **kwargs,
        )

    return wrapper


def Button(
    label: str | None = None,
    *,
    clicked: Callable[[], None] | None = None,
    tool: bool = False,
    icon: QIcon | str | None = None,
    stretch: int = 0,
    alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
    add: bool = True,
    **kwargs: KwArgs,
) -> QAbstractButton:
    """
    Button Widget.

    Example:
    ~:code:../examples/ui/widgets.py[buttons]:~

    :param str label: text of the button, defaults to None
    :param bool tool: use tool style button, defaults to False
    :param Union[QIcon, str] icon: icon, defaults to None
    :param int stretch: layout stretch, defaults to 0
    :param Qt.Alignment alignment: layout alignment, defaults to Qt.Alignment()
    :param bool add: add to current context, defaults to True
    :return QAbstractButton: The widget
    """
    btn = QToolButton() if tool else QPushButton()
    set_qt_attrs(btn, **kwargs)

    if label:
        btn.setText(label)
    elif "text" not in kwargs:
        btn.setText("Button")

    if isinstance(icon, QIcon):
        btn.setIcon(icon)
    elif isinstance(icon, str):
        btn.setIcon(QIcon(icon))

    if add:
        place_widget(btn, stretch=stretch, alignment=alignment)

    btn.clicked.connect(clicked)
    return btn


##% [Gui] ProgressIndicator
##% ────────────────────────────────────────────────────────────────────────────
class ProgressIndicator:
    """Wrapper required because there is a bug with Base.ProgressIndicator on MacOS."""

    def __init__(self, *args: tuple, **kwargs: KwArgs) -> None:
        try:
            self.control = Base.ProgressIndicator(*args, **kwargs)
        except Exception:  # noqa: BLE001
            self.control = None

    def start(self, *args: tuple, **kwargs: KwArgs) -> None:
        if self.control:
            self.control.start(*args, **kwargs)

    def next(self, *args: tuple, **kwargs: KwArgs) -> None:
        if self.control:
            self.control.next(*args, **kwargs)

    def stop(self, *args: tuple, **kwargs: KwArgs) -> None:
        if self.control:
            self.control.stop(*args, **kwargs)


##% [Context] progress_indicator
##% ────────────────────────────────────────────────────────────────────────────
@contextmanager
def progress_indicator(
    message: str | None = None,
    steps: int = 0,
) -> Generator[ProgressIndicator, None, None]:
    """
    Indicator of progress context manager

    Example:
    ~:code:../examples/ui/widgets.py[progress_indicator]:~

    :param str message: Message, defaults to 'Working...'
    :param int steps: max number of steps, defaults to 0
    :yield ProgressIndicator: The progress indicator controller
    """
    bar = ProgressIndicator()
    bar.start(message or _tr_working, steps)
    try:
        yield bar
    finally:
        bar.stop()
        del bar


##% [Widget Impl] SvgImageViewWidget
##% ────────────────────────────────────────────────────────────────────────────
class SvgImageViewWidget(QWidget):
    """High resolution Svg Widget."""

    def __init__(self, uri: str) -> None:
        super().__init__()
        self.uri = uri
        self._size = (0, 0)
        self._renderer = None
        self.update_img(QRect(QPoint(0, 0), self.size()))

    def update_img(self, rect: QRect) -> None:
        if not self.uri or not Path(self.uri).exists():
            return

        renderer = QSvgRenderer(self.uri, self)
        view_box = renderer.viewBoxF()

        width, height = 0, 0
        r_width, r_height = rect.width(), rect.height()
        svg_width, svg_height = view_box.width(), view_box.height()

        if svg_width <= 0 or svg_height <= 0:
            svg_width = r_width
            svg_height = r_height

        scale_w, scale_h = 1.0, 1.0
        if svg_width > 0 and r_width > 0:
            scale_w = r_width / svg_width
        if svg_height > 0 and r_height > 0:
            scale_h = r_height / svg_height

        scale = min(scale_h, scale_w)
        width = svg_width * scale
        height = svg_height * scale

        self._renderer = renderer
        self._size = (width, height)
        self.setMinimumSize(width, height)

    def paintEvent(self, e: QPaintEvent) -> None:
        qp = QPainter(self)
        try:
            rect = e.rect()
            if (
                self._size == (0, 0)
                or self._size != (rect.width(), rect.height())
                or self._renderer is None
            ):
                self.update_img(rect)
            if self._renderer:
                qp.save()
                qp.setViewport(0, 0, *self._size)
                self._renderer.render(qp)
                qp.restore()
        finally:
            qp.end()

    def setValue(self, uri: str) -> None:
        self.uri = uri
        self._renderer = None
        self.update()

    def value(self) -> str:
        return self.uri


##% [Widget Impl] ImageViewWidget
##% ────────────────────────────────────────────────────────────────────────────
class ImageViewWidget(QLabel):
    """Basic Image Widget."""

    def __init__(self, uri: str, background: QColor | str | None = None) -> None:
        super().__init__()
        self.uri = uri
        self._pixmap = QPixmap(uri)
        self._bg = None
        if isinstance(background, QColor):
            self._bg = background
        elif isinstance(background, str):
            self._bg = Color(code=background)

    def setValue(self, uri: str) -> None:
        self._pixmap = QPixmap(uri)
        self.update()

    def value(self) -> str:
        return self.uri

    def paintEvent(self, e: QPaintEvent) -> None:
        qp = QPainter(self)
        try:
            qp.setRenderHint(QPainter.SmoothPixmapTransform)
            winSize = e.rect()
            if self._bg:
                qp.fillRect(winSize, self._bg)
            pixmapRatio = (
                float(self._pixmap.width()) / self._pixmap.height()
                if self._pixmap.height()
                else 1.0
            )
            windowRatio = float(winSize.width()) / winSize.height() if winSize.height() else 1.0
            if pixmapRatio < windowRatio:
                newWidth = int(winSize.height() * pixmapRatio)
                qp.drawPixmap(0, 0, newWidth, winSize.height(), self._pixmap)
            else:
                newHeight = int(winSize.width() / pixmapRatio)
                qp.drawPixmap(0, 0, winSize.width(), newHeight, self._pixmap)
        finally:
            qp.end()


##% [Widget] ImageView
##% ────────────────────────────────────────────────────────────────────────────
def ImageView(
    uri: str,
    *,
    label: str | None = None,
    name: str | None = None,
    background: str | QColor | None = None,
    add: bool = True,
    **kwargs: KwArgs,
) -> ImageViewWidget:
    """
    Image render widget.

    Example:
    ~:code:../examples/ui/widgets.py[ImageView]:~

    :param str uri: path to load the image from
    :param str label: gui label, defaults to None
    :param str name: objectName, defaults to None
    :param Union[str, QColor] background: background color, defaults to None
    :param bool add: _description_, defaults to True
    :return ImageViewWidget: _description_
    """
    widget = ImageViewWidget(uri, background)
    if name:
        widget.setObjectName(name)
    set_qt_attrs(widget, **kwargs)
    if add:
        place_widget(widget, label=label)
    return widget


##% [Widget] SvgImageView
##% ────────────────────────────────────────────────────────────────────────────
def SvgImageView(
    uri: str,
    label: str | None = None,
    *,
    name: str | None = None,
    stretch: int = 0,
    alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
    **kwargs: KwArgs,
) -> SvgImageViewWidget:
    """
    High resolution Svg Image box.

    Example:
    ~:code:../examples/ui/widgets.py[SvgImageView]:~

    :param str uri: file path if the svg
    :param str name: Widget name, defaults to None
    :return SvgImageViewWidget: The widget
    """
    widget = SvgImageViewWidget(uri)
    if name:
        widget.setObjectName(name)
    set_qt_attrs(widget, **kwargs)
    place_widget(widget, label, stretch=stretch, alignment=alignment)
    return widget


##% [Widget Impl] TableWidget
##% ────────────────────────────────────────────────────────────────────────────
class TableWidget(QTableWidget):
    """Basic grid visualization widget."""

    def __init__(self, headers: list[str], rows: list[list[Any]]) -> None:
        num_rows = len(rows)
        num_cols = len(headers)
        super().__init__(num_rows, num_cols)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        def column(col_spec: str) -> tuple[str, Qt.Alignment]:
            if col_spec.startswith("<"):
                return (col_spec[1:], Qt.AlignLeft)
            if col_spec.startswith(">"):
                return (col_spec[1:], Qt.AlignRight)
            if col_spec.startswith("^"):
                return (col_spec[1:], Qt.AlignCenter)
            return (col_spec, Qt.AlignLeft)

        aligns = []
        for col in range(num_cols):
            text, align = column(str(headers[col]))
            aligns.append(align | Qt.AlignVCenter)
            item = QTableWidgetItem(text)
            item.setTextAlignment(align | Qt.AlignVCenter)
            self.setHorizontalHeaderItem(col, item)

        self.num_cols = num_cols
        self.aligns = aligns
        self.setRowsData(rows)

    def setRowsData(self, rows: list[list[Any]]) -> None:
        num_rows = len(rows)
        aligns = self.aligns
        self.setRowCount(0)  # Force Clean
        self.setRowCount(num_rows)
        for row in range(num_rows):
            row_data = rows[row]
            for col in range(min(self.num_cols, len(row_data))):
                text, align = row_data[col], aligns[col]
                item = QTableWidgetItem("" if text is None else str(text))
                item.setTextAlignment(align)
                self.setItem(row, col, item)


##% [Widget Impl] Table
##% ────────────────────────────────────────────────────────────────────────────
def Table(
    headers: list[str],
    rows: list[list[Any]],
    *,
    name: str | None = None,
    stretch: int = 0,
    alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
    add: bool = True,
    **kwargs: KwArgs,
) -> TableWidget:
    """
    Simple Table output widget.

    Example:
    ~:code:../examples/ui/widgets.py[Table]:~

    :param list[str] headers: column headers
    :param list[list[Any]] rows: data
    :param str name: objectName, defaults to None
    :param int stretch: layout stretch, defaults to 0
    :param Qt.Alignment alignment: layout alignment, defaults to Qt.Alignment()
    :param bool add: add to current context, defaults to True
    :return TableWidget: The table widget
    """
    table = TableWidget(headers, rows)
    set_qt_attrs(table, **kwargs)
    if name:
        table.setObjectName(name)
    if add:
        place_widget(table, stretch=stretch, alignment=alignment)
    return table


##% [Concurrency] Main Thread Hook
##% ────────────────────────────────────────────────────────────────────────────
class _ui_thread_hook_class(QObject):
    """Special bridge to send method calls to main thread (ui thread)."""

    queued = Signal(object)

    def __init__(self) -> None:
        super().__init__(QApplication.instance())
        self.moveToThread(QApplication.instance().thread())
        self.queued.connect(self.run, Qt.QueuedConnection)

    def send(self, func: Callable) -> None:
        """
        Enqueue the callable object `func` to execute in main thread as soon as possible.

        Callable from any thread.
        """
        self.queued.emit(func)

    @Slot(object)
    def run(self, func: Callable) -> None:
        """Runs the callable `func` in main thread."""
        func()


##@ [Decorator] ui_thread
##@ ────────────────────────────────────────────────────────────────────────────
def ui_thread(delay: int = 0) -> Callable:
    """
    Decorator for running callables in Qt's UI Thread.

    :param int delay: delay in milliseconds
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args: tuple, **kwargs: KwArgs) -> None:
            if delay > 0:
                _ui_thread_hook_obj.send(
                    lambda: QTimer.singleShot(
                        delay,
                        lambda: f(*args, **kwargs),
                    ),
                )
            else:
                _ui_thread_hook_obj.send(lambda: f(*args, **kwargs))

        return wrapper

    return decorator


##% [Helper] CanvasHelper
##% ────────────────────────────────────────────────────────────────────────────
class CanvasHelper:
    """Provides contextual styles for canvas related tasks."""

    def __init__(self, widget: QWidget, painter: QPainter, event: QPaintEvent) -> None:
        self.widget = widget
        self.painter = painter
        self.event = event

    def setBackgroundColor(self, color: QColor) -> None:
        self.painter.fillRect(self.event.rect(), color)

    @contextmanager
    def pen(self, **kwargs: KwArgs) -> Generator[QPen, None, None]:
        self._old_pen = self.painter.pen()
        pen = QPen()
        set_qt_attrs(pen, **kwargs)
        self.painter.setPen(pen)
        yield pen
        self.painter.setPen(self._old_pen)

    @contextmanager
    def brush(self, **kwargs: KwArgs) -> Generator[QBrush, None, None]:
        self._old_brush = self.painter.brush()
        brush = QBrush()
        set_qt_attrs(brush, **kwargs)
        self.painter.setBrush(brush)
        yield brush
        self.painter.setBrush(self._old_brush)


##% [Widget Impl] CanvasWidget
##% ────────────────────────────────────────────────────────────────────────────
class CanvasWidget(QWidget):
    """Basic canvas widget."""

    def __init__(
        self,
        *,
        paint: Callable[[QWidget, QPainter, QPaintEvent], None] | None = None,
        setup: Callable[[QWidget, QPainter, QPaintEvent], None] | None = None,
        parent: QWidget = None,
    ) -> None:
        super().__init__(parent)
        self._paint = paint
        self._setup = setup

    def paintEvent(self, e: QPaintEvent) -> None:
        qp = QPainter(self)
        qp.save()
        helper = CanvasHelper(self, qp, e)
        try:
            if self._setup:
                self._setup(self, qp, helper)
            if self._paint:
                self._paint(self, qp, helper)
        finally:
            qp.restore()
            qp.end()


##% [Widget] Canvas
##% ────────────────────────────────────────────────────────────────────────────
def Canvas(
    paint: Callable[[QWidget, QPainter, QPaintEvent], None],
    *,
    setup: Callable[[QWidget, QPainter, QPaintEvent], None] | None = None,
    name: str | None = None,
    stretch: int = 0,
    width: int = 0,
    height: int = 0,
    **kwargs: KwArgs,
) -> CanvasWidget:
    """
    Canvas Widget to allow custom painting.

    Example:
    ~:code:../examples/ui/widgets.py[Canvas]:~

    :param Callable[[QWidget, QPainter, QPaintEvent], None] paint: function to paint
    :param Callable[[QWidget, QPainter, QPaintEvent], None] setup: function to setup canvas
    :param str name: objectName, defaults to None
    :param int stretch: layout stretch, defaults to 0
    :param int width: minimum width, defaults to 0
    :param int height: minimum height, defaults to 0
    :return CanvasWidget: The widget
    """
    widget = CanvasWidget(paint=paint, setup=setup)
    widget.setMinimumSize(width, height)
    set_qt_attrs(widget, **kwargs)
    if name:
        widget.setObjectName(name)
    place_widget(widget, stretch=stretch, alignment=Qt.AlignVCenter | Qt.AlignCenter)
    return widget


##% [Widget Impl] HeaderWidget
##% ────────────────────────────────────────────────────────────────────────────
class HeaderWidget(QWidget):
    """Basic header label."""

    def __init__(self, text: str, *, line: bool = True, **kwargs: KwArgs) -> None:
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        label = QLabel(text)
        label.setStyleSheet("font-weight: bold")
        label.setProperty("styleClass", "header-label")
        set_qt_attrs(label, **kwargs)
        layout.addWidget(label)

        if line:
            sep = QFrame()
            label.setProperty("styleClass", "header-line")
            sep.setFrameShape(QFrame.HLine)
            sep.setFrameShadow(QFrame.Sunken)
            layout.addWidget(sep)


##% [Widget] Header
##% ────────────────────────────────────────────────────────────────────────────
def Header(text: str, *, add: bool = True, **kwargs: KwArgs) -> HeaderWidget:
    """
    Simple header label.

    Example:
    ~:code:../examples/ui/widgets.py[Header]:~

    :param str text: the text
    :param bool add: add to current context, defaults to True
    :return HeaderWidget: the widget
    """
    widget = HeaderWidget(text, **kwargs)
    if add:
        place_widget(widget)
    return widget


##% [Widget Impl] LogViewWidget
##% ────────────────────────────────────────────────────────────────────────────
class LogViewWidget(QPlainTextEdit):
    """Log console widget."""

    def __init__(
        self,
        style: str | None = None,
        err_style: str | None = None,
        warn_style: str | None = None,
    ) -> None:
        super().__init__()
        self.style = style
        self.err_style = err_style or ""
        self.warn_style = warn_style or ""
        if style:
            self.setStyleSheet(style)
        self.setReadOnly(True)
        self.setCenterOnScroll(True)

    def info(self, message: str) -> None:
        self.appendHtml(f"<p>{message}</p>")
        self.ensureCursorVisible()

    def error(self, message: str) -> None:
        self.appendHtml(f"<p style='{self.err_style}'>{message}</p>")
        self.ensureCursorVisible()

    def warn(self, message: str) -> None:
        self.appendHtml(f"<p style='{self.warn_style}'>{message}</p>")
        self.ensureCursorVisible()


##% [Widget] LogView
##% ────────────────────────────────────────────────────────────────────────────
def LogView(
    *,
    style: str | None = None,
    err_style: str | None = None,
    warn_style: str | None = None,
    add: bool = True,
    **kwargs: KwArgs,
) -> LogViewWidget:
    """Basic log console widget."""
    widget = LogViewWidget(style, err_style, warn_style)
    set_qt_attrs(widget, **kwargs)
    if add:
        place_widget(widget)
    return widget


##% [Widget] Section
##% ────────────────────────────────────────────────────────────────────────────
@contextmanager
def Section(
    header: QWidget | str,
    indent: int = 0,
    **kwargs: KwArgs,
) -> Generator[QWidget, None, None]:
    with Container():
        with Col(contentsMargins=(indent, 0, 0, 0), spacing=0):
            if isinstance(header, QWidget):
                place_widget(header)
            else:
                Header(header)
            with Container(contentsMargins=(indent, 0, 0, 0)):
                yield Container(**kwargs)


##% [Widget] InputColor
##% ────────────────────────────────────────────────────────────────────────────
class InputColorWidget(QPushButton):
    """Widget for color selection."""

    def __init__(self, *, value: Any = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.setValue(value or "rgba(0,0,0,255)")
        self.dirty = True

    def value(self) -> str:
        return str(self._color)

    def setValue(self, color: str | Color) -> None:
        self._color = color if isinstance(color, Color) else Color(color)
        self.dirty = True
        self.update()

    def getValueColor(self) -> Color:
        return self._color

    def paintEvent(self, e: QPaintEvent) -> None:
        if self.dirty:
            isize = self.iconSize()
            pix = QPixmap(isize)
            pix.fill(self.palette().button().color())
            p = QPainter(pix)
            w = pix.width()
            h = pix.height()
            p.setBrush(self._color)
            p.fillRect(0, 0, w, h, QBrush(self._color))
            p.setPen(QPen(Qt.gray))
            p.drawRect(0, 0, w - 1, h - 1)
            p.end()
            self.setIcon(QIcon(pix))
            self.dirty = False

        super().paintEvent(e)


def InputColor(
    value: str = "rgba(0,0,0,255)",
    *,
    name: str | None = None,
    label: QWidget | str = None,
    stretch: int = 0,
    alignment: Qt.Alignment = DEFAULT_ALIGNMENT,
    add: bool = True,
    **kwargs: KwArgs,
) -> InputColorWidget:
    widget = InputColorWidget(value=value)
    set_qt_attrs(widget, **kwargs)

    if name:
        widget.setObjectName(name)

    def trigger() -> None:
        if color := choose_color(caption=label or "Choose Color", initial=widget.getValueColor()):
            widget.setValue(Color(color))

    widget.clicked.connect(trigger)
    if add:
        place_widget(widget, label=label, stretch=stretch, alignment=alignment)

    return widget


update_wrapper(InputColor, button)


##% [Widget] TaskPanel
##% ────────────────────────────────────────────────────────────────────────────
class TaskPanelAdapter(QObject):
    """Adapter for Task Panels."""

    def __init__(self, view: TaskPanel, parent: QObject = None) -> None:
        super().__init__(parent)
        self.view = view
        self.form = view.build()

    def deactivate(self, *, recompute: bool = False) -> None:
        if (doc := App.ActiveDocument) and recompute:
            doc.recompute()
            App.Gui.ActiveDocument.resetEdit()
        if App.Gui.Control.activeDialog():
            App.Gui.Control.closeDialog()
        self.view.on_close()

    def accept(self) -> None:
        self.view.on_accept()
        self.deactivate(recompute=True)

    def reject(self) -> None:
        self.view.on_reject()
        self.deactivate()


class TaskPanel:
    """TaskPanel base class."""

    dialog: TaskPanelAdapter = None

    def build(self) -> QWidget:
        raise NotImplementedError

    def on_accept(self) -> None:
        pass

    def on_reject(self) -> None:
        pass

    def on_close(self) -> None:
        pass

    def show(self) -> None:
        self.close()
        self.dialog = TaskPanelAdapter(self)
        App.Gui.Control.showDialog(self.dialog)

    def close(self) -> None:
        if self.dialog:
            self.dialog.deactivate()
            self.dialog = None
        if App.Gui.Control.activeDialog():
            App.Gui.Control.closeDialog()


##: [SECTION] Utility functions
##: ────────────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────────────
def set_indicator_icon(
    widget: QWidget,
    icon: str | QIcon | None,
    pos: QLineEdit.ActionPosition | None = None,
) -> None:
    """Adds an icon to a QLineEdit or any widget that has lineEdit() method."""
    target = None
    if isinstance(widget, QLineEdit):
        target = widget
    elif lineEdit := getattr(widget, "lineEdit", None):
        target = lineEdit()

    if not target:
        return

    if old := getattr(widget, "_fcapi_icon", None):
        target.removeAction(old)
        widget._fcapi_icon = None  # noqa: SLF001

    if isinstance(icon, QIcon):
        widget._fcapi_icon = target.addAction(icon, pos or QLineEdit.LeadingPosition)  # noqa: SLF001
    elif isinstance(icon, str):
        widget._fcapi_icon = target.addAction(  # noqa: SLF001
            QIcon.fromTheme(icon),
            pos or QLineEdit.LeadingPosition,
        )
    else:
        return

    def clear(*_args) -> None:
        target.textEdited.disconnect(clear)
        target.removeAction(widget._fcapi_icon)  # noqa: SLF001
        widget._fcapi_icon = None  # noqa: SLF001

    target.textEdited.connect(clear)


# ──────────────────────────────────────────────────────────────────────────────
def margins(
    left: int = 0,
    top: int = 0,
    right: int = 0,
    bottom: int = 0,
) -> QMargins:
    """Margins."""
    return QMargins(left, top, right, bottom)


# ──────────────────────────────────────────────────────────────────────────────
def update_style(widget: QWidget) -> None:
    """
    Force widget style refresh.

    :param QWidget widget: the widget
    """
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


# ──────────────────────────────────────────────────────────────────────────────
def choose_color(
    caption: str | None = None,
    initial: QColor | None = None,
) -> QColor | None:
    color = QColorDialog.getColor(
        initial=initial or Qt.white,
        title=caption,
        options=QColorDialog.ColorDialogOption.ShowAlphaChannel,
    )
    return color if color.isValid() else None


# ──────────────────────────────────────────────────────────────────────────────
def get_open_file(caption: str | None = None, filter: str | None = None) -> str | None:
    """
    Open File Dialog.

    :param str caption: dialog title, defaults to "Open"
    :param _type_ filter: filter pattern, defaults to None
    :return _type_: selected file name
    """
    names = QFileDialog.getOpenFileName(
        QApplication.activeWindow(),
        caption=caption or _tr_open,
        filter=filter,
    )
    if names and names[0]:
        return names[0]
    return None


# ──────────────────────────────────────────────────────────────────────────────
def get_save_file(
    caption: str | None = None,
    filter: str | None = None,
    file: str | None = None,
) -> str | None:
    """
    Save File Dialog.

    :param str caption: dialog title, defaults to Save
    :param str filter: filter pattern, defaults to None
    :param str file: default filename, defaults to None
    :return str: target file name
    """
    names = QFileDialog.getSaveFileName(
        QApplication.activeWindow(),
        caption=caption or _tr_save,
        dir=file,
        filter=filter,
    )
    if names and names[0]:
        return names[0]
    return None


# ──────────────────────────────────────────────────────────────────────────────
def load_font(path: str) -> None:
    """
    Load font into Qt.

    :param str path: filesystem path to the font
    """
    QFontDatabase.addApplicationFont(path)


# ──────────────────────────────────────────────────────────────────────────────
@ui_thread(delay=10)
def show_info(
    message: str,
    title: str | None = None,
    std_icon: Any = QMessageBox.Information,  # typing not avail
    std_buttons: Any = QMessageBox.Ok,  # typing not avail
    parent: QWidget | None = None,
) -> None:
    """Basic Message Box."""
    diag = QMessageBox(parent or find_active_window())
    diag.setIcon(std_icon)
    diag.setWindowTitle(str(title) if title else _tr_information)
    diag.setText(str(message))
    diag.setStandardButtons(std_buttons)
    diag.open()


# ──────────────────────────────────────────────────────────────────────────────
def confirm(
    question: str,
    *,
    title: str | None = None,
    description: str | None = None,
    std_icon: Any = QMessageBox.Question,
    std_buttons: Any = QMessageBox.Yes | QMessageBox.No,
    parent: QWidget | None = None,
) -> bool:
    """Basic Message Box."""
    diag = QMessageBox(parent or find_active_window())
    diag.setIcon(std_icon)
    diag.setWindowTitle(str(title) if title else _tr_question)
    diag.setText(str(question))
    diag.setStandardButtons(std_buttons)
    diag.setWindowModality(Qt.WindowModality.ApplicationModal)
    if description:
        diag.setInformativeText(str(description))
    diag.exec()
    ret = diag.buttonRole(diag.clickedButton())
    roles = QMessageBox.ButtonRole
    return ret in {
        roles.AcceptRole,
        roles.ActionRole,
        roles.ApplyRole,
        roles.YesRole,
    }


# ──────────────────────────────────────────────────────────────────────────────
def show_warning(
    message: str,
    title: str | None = None,
    std_icon: Any = QMessageBox.Warning,
    std_buttons: Any = QMessageBox.Ok,
    parent: QWidget = None,
) -> None:
    """Warning message box."""
    show_info(message, title or _tr_warning, std_icon, std_buttons, parent)


# ──────────────────────────────────────────────────────────────────────────────
def show_error(
    message: str,
    title: str | None = None,
    std_icon: Any = QMessageBox.Critical,
    std_buttons: Any = QMessageBox.Ok,
    parent: QWidget = None,
) -> None:
    """Error message box."""
    show_info(message, title or _tr_error, std_icon, std_buttons, parent)


# ──────────────────────────────────────────────────────────────────────────────
def qt_get_widget_path(widget: QWidget, index: int) -> str:
    """
    Return a string representation of widget hierarchy position as a path.

    i.e. root/mainWindow/QFrame/QLabel_1
    """
    name = widget.objectName()
    if not name:
        name = f"{widget.__class__.__name__}_{index}"
    path = [name]
    parent = widget.parent()
    while parent:
        path.append(parent.objectName() or parent.__class__.__name__)
        parent = parent.parent()
    return "/".join(reversed(path))


# ──────────────────────────────────────────────────────────────────────────────
def save_widget_state(widget: QWidget, file: Path | str) -> None:
    """Dump all values of child nodes into file in json format."""
    data = {}
    index = 0
    for child in widget.findChildren(QWidget):
        if hasattr(child, "value"):
            path = qt_get_widget_path(child, index)
            index += 1
            try:
                data[path] = child.value()
            except Exception:  # noqa: BLE001
                print_log(f"Ignoring value of {path}")
    with open(file, "w") as f:
        f.write(json.dumps(data))


# ──────────────────────────────────────────────────────────────────────────────
def load_widget_state(widget: QWidget, file: str | Path) -> None:
    """Load values from json file into widget child nodes."""
    file = Path(file)
    if not file.exists():
        print_err(f"{file!s} does not exists.")
        return

    with open(file) as f:
        data = json.load(f)
        index = 0
        for child in widget.findChildren(QWidget):
            if hasattr(child, "setValue"):
                path = qt_get_widget_path(child, index)
                index += 1
                if path in data:
                    try:
                        child.setValue(data[path])
                    except Exception:  # noqa: BLE001
                        print_log(f"Ignoring value of {path} because it was not found")


# ──────────────────────────────────────────────────────────────────────────────
def find_active_window() -> Gui.MainWindowPy | QDialog | QMainWindow:
    """Return the current active window."""
    focus = QApplication.focusWidget()
    if focus:
        parent = focus.parent()
        if isinstance(parent, (QDialog, QMainWindow)) and parent.isVisible():
            return parent
    return Gui.getMainWindow()


# ──────────────────────────────────────────────────────────────────────────────
def get_tr(context: str) -> Callable[[str], str]:
    """
    Returns a translation function for the given context.

    :param str context: translation context
    :return Callable[[str], str]: translation function
    """

    def tr(text: str) -> str:
        return QApplication.translate(context, text)

    return tr


# ──────────────────────────────────────────────────────────────────────────────
def print_log(*args: tuple) -> None:
    """Print to console."""
    App.Console.PrintLog(f"[{_tr_info}] {' '.join(str(a) for a in args)}\n")


# ──────────────────────────────────────────────────────────────────────────────
def print_err(*args: tuple) -> None:
    """Print to console."""
    App.Console.PrintError(f"[{_tr_error}] {' '.join(str(a) for a in args)}\n")


# ──────────────────────────────────────────────────────────────────────────────
def to_vec(input: Any) -> Vector:  # noqa: PLR0911
    """Convert tuple/list/vector/object to Vector."""
    if isinstance(input, Vector):
        return input
    if isinstance(input, (tuple, list)):
        if len(input) == 3:  # noqa: PLR2004
            return Vector(*input)
        if len(input) == 2:  # noqa: PLR2004
            return Vector(*input, 0)
        if len(input) == 1:
            return Vector(*input, 0, 0)
    if isinstance(input, (float, int)):
        return Vector(input, 0, 0)
    if hasattr(input, "X"):
        if hasattr(input, "Y"):
            if hasattr(input, "Z"):
                return Vector(input.X, input.Y, input.Z)
            return Vector(input.X, input.Y, 0)
        return Vector(input.X, 0, 0)
    msg = f"Invalid input, {type(input)} is not convertible to Vector"
    raise TypeError(msg)


##: [SECTION] Module translations (i18n)
##: ────────────────────────────────────────────────────────────────────────────

_tr = get_tr("fcui")
_tr_info = _tr("Info")
_tr_error = _tr("Error")
_tr_add = _tr("Add")
_tr_remove = _tr("Remove")
_tr_clean = _tr("Clean")
_tr_object = _tr("Object")
_tr_sub_object = _tr("SubObject")
_tr_working = _tr("Working...")
_tr_open = _tr("Open")
_tr_save = _tr("Save")
_tr_information = _tr("Information")
_tr_question = _tr("Question")
_tr_warning = _tr("Warning")
_tr_select = _tr("Select...")

##: [SECTION] Globals
##: ────────────────────────────────────────────────────────────────────────────

# Global Main Thread hook
_ui_thread_hook_obj = _ui_thread_hook_class()

# UI Builders are not thread safe, so each thread has its own state.
_thread_local_gui_vars = threading.local()

# FreeCAD UI loader to access custom widgets
_fc_ui_loader = Gui.UiLoader()

# SPDX-License: LGPL-3.0-or-later
# (c) 2024 Frank David Martínez Muñoz. <mnesarco at gmail.com>

from __future__ import annotations
from contextlib import contextmanager
from typing import Any, TYPE_CHECKING

import FreeCAD as App  # type: ignore

if TYPE_CHECKING:
    from collections.abc import Callable, Generator


class ShibokenLoader:
    """Lazy loader for shiboken"""

    def __init__(self) -> None:  # noqa: D107
        self._ref_is_valid = None

    @property
    def ref_is_valid(self) -> Callable[[Any], bool]:
        if fn := self._ref_is_valid:
            return fn

        import PySide  # type: ignore

        if int(PySide.QtCore.qVersion().split(".")[0]) == 5:  # noqa: PLR2004
            from shiboken2 import isValid  # type: ignore
        else:
            from shiboken6 import isValid

        self._ref_is_valid = isValid
        return isValid


_ShibokenLoader = ShibokenLoader()


def ref_is_valid(target: Any) -> bool:
    return _ShibokenLoader.ref_is_valid(target)


def run_later(callback: Callable) -> None:
    from PySide.QtCore import QTimer  # type: ignore

    QTimer.singleShot(0, callback)


@contextmanager
def recompute_buffer(
    doc: App.Document | None = None,
    *,
    flush: bool = True,
) -> Generator[None, Any, None]:
    doc = doc or App.ActiveDocument
    if doc.RecomputesFrozen:
        yield
    else:
        try:
            doc.RecomputesFrozen = True
            yield
        except Exception:
            doc.RecomputesFrozen = False
            raise
        else:
            doc.RecomputesFrozen = False
            if flush:
                doc.recompute()

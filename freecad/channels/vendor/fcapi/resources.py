# SPDX-License: LGPL-3.0-or-later
# (c) 2024 Frank David Martínez Muñoz. <mnesarco at gmail.com>

import importlib.resources
import FreeCAD as App # type: ignore
from pathlib import Path
import importlib
from .events import events
from types import ModuleType

class Resources:
    """Addon resource manager"""

    def __init__(self, module: ModuleType) -> None:
        self._base = Path(App.getResourceDir())
        self._user = Path(App.getUserAppDataDir())
        self._macro = App.getUserMacroDir(True)
        self._mod = self._base / "Mod"
        self._pkg = importlib.resources.files(module)
        self._module = module
        self._initialized = False

    def icon(self, path: str) -> str:
        base = self._pkg / "icons"
        return str(base.joinpath(path))

    def __call__(self, path: str) -> str:
        t_path = self._pkg
        for part in path.split("/"):
            t_path = t_path / part
        return str(t_path)

    @events.app.gui_up
    def on_gui(self, _event) -> None:
        if not self._initialized:
            icons = str(self._pkg / "icons")
            translations = str(self._pkg / "translations")
            App.Console.PrintLog(f"Installing {self.__class__.__qualname__}: icons={icons}\n")
            App.Gui.addIconPath(str(self._pkg / "icons"))
            App.Console.PrintLog(f"Installing {self.__class__.__qualname__}: translations={translations}\n")
            App.Gui.addLanguagePath(translations)
            App.Gui.updateLocale()
        self._initialized = True

# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

import importlib
from rich import print  # noqa: A004
from pathlib import Path
import sys


# ----------------------------------------------------
# Find freecad.*.vendor.fcapi.devutils
# ----------------------------------------------------
cwd = Path(__file__).parent
paths = list(cwd.glob("**/vendor/fcapi/devutils/build.py"))
if not paths:
    print("[red]fcapi.devutils not found")
    sys.exit(1)

# ----------------------------------------------------
# Dynamically import vendored freecad.*.vendor.fcapi.devutils
# ----------------------------------------------------
build_path = paths[0].relative_to(cwd)
module_name = ".".join(build_path.parts[:-1]) + ".build"
build = importlib.import_module(module_name, ".")

# # Launch
# ----------------------------------------------------
if __name__=="__main__":
    build.app()


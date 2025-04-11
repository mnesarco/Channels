# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    import FreeCAD as App  # type: ignore


def temp(name: str, ext: str) -> Path:
    parent = Path.home() / ".freecad" / "channels"
    parent.mkdir(parents=True, exist_ok=True)
    return parent / f"{name}.{ext}"


def export_obj(objects: list[App.DocumentObject]) -> Path:
    from importers import importOBJ  # type: ignore

    filename = temp(str(uuid4()), "obj")
    if hasattr(importOBJ, "exportOptions"):
        options = importOBJ.exportOptions(str(filename))
        importOBJ.export(objects, str(filename), options)
    else:
        importOBJ.export(objects, str(filename))

    # Workaround to importOBJ.export BUG.
    # importOBJ.export references mtl file but may not create it.
    mtl = filename.with_suffix(".mtl")
    if not mtl.exists():
        with mtl.open("w", encoding="utf-8") as f:
            f.write("# Created by FreeCAD\n")

    return filename


def export_gltf(objects: list[App.DocumentObject]) -> Path:
    import ImportGui  # type: ignore

    filename = temp(str(uuid4()), "gltf")
    if hasattr(ImportGui, "exportOptions"):
        options = ImportGui.exportOptions(str(filename))
        ImportGui.export(objects, str(filename), options)
    else:
        ImportGui.export(objects, str(filename))

    return filename

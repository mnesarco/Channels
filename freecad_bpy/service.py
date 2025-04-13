# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

"""
FreeCAD Channels for Blender.
"""

from __future__ import annotations

from logging import StreamHandler, getLogger

import bmesh
import bpy

from .bpy_channels import channel_handler, ServiceRequest
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

logger = getLogger("FreeCAD.Channels")
logger.setLevel("INFO")
logger.addHandler(StreamHandler())


@channel_handler(name="Blender", queue_size=50)
def service(req: ServiceRequest) -> None:
    """
    Handle service requests for Blender.

    This function processes incoming service requests and performs
    actions based on the request data. Currently, it supports the
    'import_file' action, which triggers the import of a file into
    Blender.

    :param req: The service request containing action and data.
    """
    match req.data:
        case {"action": "import_file", "path": path}:
            action_import_file(path)
        case _:
            logger.warning("Unknown request: %s", req)


def action_import_file(path: str) -> None:
    """
    Handle import_file action in service request.

    This function is called by the service when an 'import_file' action
    is requested. It checks if the file exists, and if so, imports it
    into Blender using an appropriate import operator.

    :param path: The path to the file to import.
    """
    path = Path(path)
    if not Path(path).exists():
        logger.warning("File does not exists: %s", str(path))
        return

    match path.suffix.lower():
        case ".obj":
            import_file(
                path,
                lambda path: bpy.ops.wm.obj_import(
                    filepath=str(path),
                    forward_axis="Y",
                    up_axis="Z",
                ),
            )
        case ".gltf":
            import_file(
                path,
                lambda path: bpy.ops.import_scene.gltf(
                    filepath=str(path),
                ),
            )
        case _:
            logger.warning("Unknown file format: %s", str(path))


def import_objects(path: str, operator: Callable[[str], None]) -> list[str]:
    """
    Import a file and return the names of the new objects created.

    :param path: Path to the file to import.
    :param operator: Callable that takes a path and imports the file.
    :return: A set of names of objects created during the import.
    """
    before = {obj.name for obj in bpy.data.objects}
    operator(path)
    after = {obj.name for obj in bpy.data.objects}
    return after - before


def import_file(path: str, operator: Callable[[str], None]) -> None:
    """
    Import a file and replace the mesh data of existing objects.

    :param path: Path to the file to import.
    :param operator: Callable that takes a path and imports the file.

    This function imports a file and checks if an objects with the same
    name already exists. If it does, it copies the
    mesh data from the imported objects to the existing objects and then
    deletes the imported objects.
    """
    for name in import_objects(path, operator):
        base, _, _ = name.rpartition(".")
        if base and bpy.data.objects.get(base):
            copy_mesh_data(name, base)
            delete_object(name)

def delete_object(name: str) -> None:
    """
    Delete a Blender object.

    :param name: Name of the object to delete.
    """
    bpy.ops.object.select_all(action="DESELECT")
    bpy.data.objects[name].select_set(True)
    bpy.ops.object.delete()


def copy_mesh_data(source_name: str, target_name: str) -> None:
    """
    Copy mesh data from one object to another.

    :param source_name: Name of the source object.
    :param target_name: Name of the destination object.
    """
    target = bpy.data.objects.get(target_name)
    source = bpy.data.objects.get(source_name)
    if target and source and source.data:
        bm = bmesh.new()
        bm.from_mesh(source.data)
        bm.to_mesh(target.data)
        bm.free()
        target.data.update()

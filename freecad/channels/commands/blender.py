# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

from __future__ import annotations
from pathlib import Path

import FreeCAD as App  # type: ignore

from freecad.channels.blender import send_objects, find_blender
from freecad.channels.config import commands, resources
from freecad.channels.export import export_gltf, export_obj
from freecad.channels.vendor.fcapi.lang import QT_TRANSLATE_NOOP


@commands.add(
    label=QT_TRANSLATE_NOOP("Channels", "Find blender service channel"),
    tooltip=QT_TRANSLATE_NOOP("Channels", "Find blender service channel"),
    icon=resources.icon("discover.svg"),
)
def BlenderFindService() -> None:
    from freecad.channels.vendor.fcapi.fcui import show_info, show_error

    try:
        service = find_blender(rediscover=True, timeout=5)
        if service:
            show_info(
                f"Blender service channel found at: {service.address.display}", title="Channels"
            )
        else:
            show_error("Blender service channel not found", title="Channels")
    except Exception:  # noqa: BLE001
        show_error("Failed to find Blender service channel", title="Channels")


@commands.add(
    label=QT_TRANSLATE_NOOP("Channels", "Send Objects to Blender as .obj"),
    tooltip=QT_TRANSLATE_NOOP("Channels", "Send Objects to Blender as .obj"),
    icon=resources.icon("send.svg"),
)
class BlenderSendObj:
    """Send objects to Blender using .obj format."""

    def on_activated(self) -> None:
        objects = App.Gui.Selection.getSelection()
        path = export_obj(objects)
        try:
            send_objects(path)
        except Exception:  # noqa: BLE001
            App.Console.PrintError(
                "Failed to send objects to Blender. "
                "Is FreeCAD Channels extension activated in Blender?\n",
            )

    def is_active(self) -> bool:
        selection = App.Gui.Selection.getSelection()
        return selection and all(map(is_shape, selection))


@commands.add(
    label=QT_TRANSLATE_NOOP("Channels", "Send Objects to Blender as .glTF"),
    tooltip=QT_TRANSLATE_NOOP("Channels", "Send Objects to Blender as .glTF"),
    icon=resources.icon("send.svg"),
)
class BlenderSendGltf:
    """Send objects to Blender using .glTF format."""

    def on_activated(self) -> None:
        objects = App.Gui.Selection.getSelection()
        path = export_gltf(objects)
        try:
            send_objects(path)
        except Exception:  # noqa: BLE001
            App.Console.PrintError(
                "Failed to send objects to Blender. "
                "Is FreeCAD Channels extension activated in Blender?\n",
            )

    def is_active(self) -> bool:
        selection = App.Gui.Selection.getSelection()
        return selection and all(is_shape(obj) or is_part(obj) for obj in selection)


@commands.add(
    label=QT_TRANSLATE_NOOP("Channels", "Download Blender extension for FreeCAD Channels"),
    tooltip=QT_TRANSLATE_NOOP("Channels", "Download Blender extension for FreeCAD Channels"),
    icon=resources.icon("download.svg"),
)
def BlenderDownloadExtension() -> None:
    from freecad.channels.vendor.fcapi.fcui import get_save_file
    import shutil

    file = get_save_file(
        caption=QT_TRANSLATE_NOOP("Channels", "Download Blender extension"),
        filter="*.zip",
        file="freecad_channels_4b.zip",
    )

    if file:
        source = Path(resources("files/blender/freecad_channels_4b.zip")).resolve()
        if source.exists():
            target = Path(file).resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(source), str(target))
            App.Console.PrintMessage(f"Saved to: {target}\n")


def is_shape(obj: App.DocumentObject) -> bool:
    return any(
        (
            obj.isDerivedFrom("Part::Feature"),
            obj.isDerivedFrom("Mesh::Feature"),
            obj.isDerivedFrom("App::Link"),
        ),
    )


def is_part(obj: App.DocumentObject) -> bool:
    return obj.isDerivedFrom("App::Part")

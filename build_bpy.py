# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

import zipfile

from pathlib import Path

def build(zip_file_name):
    base = Path(__file__).parent
    api = base / "freecad" / "channels" / "api"
    bpy = base / "freecad_bpy"
    out = base / "freecad" / "channels" / "resources" / "files" / "blender" / zip_file_name

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(out), "w") as zip_file:

        # API Files
        for path in api.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                zip_file.write(path, path.relative_to(base))
        zip_file.writestr("freecad/channels/__init__.py", "")
        zip_file.writestr("freecad/__init__.py", "")

        # Blender Files
        for path in bpy.rglob("*"):
            if path.is_file():
                zip_file.write(path, path.relative_to(bpy))

if __name__ == "__main__":
    build("freecad_channels_4b.zip")

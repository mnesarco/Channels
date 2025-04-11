# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

import os
import re
import tempfile
import zipfile as zf
from pathlib import Path
from typing import Annotated, Generator

import typer
from .console import print

from . import package
from .project import parse_project_toml
from .utils import BoolFlag

pkg_excluded_files = [
    r"^\.vscode",
    r"^dist/?",
    r".*\.egg-info",
    r"^\.git.*",
    r"^fcbuild\.py",
    r"\.venv/?",
    r".*/?__pycache__/?",
    r"^playground.py",
]

pkg_excluded_files_re = re.compile("|".join(pkg_excluded_files))

app = typer.Typer(
    name="fcbuild",
    help="Command line utility to build FreeCAD Addons with fcapi",
)

# Pattern to find updatable strings in python files to set the project.version
SYNC_VERSION_PATTERN_PY = re.compile("((['\"]).*?\\2)\\s*#\\s*<fcapi:sync-version>")


def scan_freecad_mods(base: Path) -> Generator[Path, None, None]:
    """Paths of all freecad submodules"""
    return (init.parent for init in base.glob("*/__init__.py"))


def update_version_py(base: Path, version: str):
    """Update project.version in __init__.py files if marked with <fcapi:sync-version>"""
    changed = BoolFlag()

    def replacer(m: re.Match) -> str:
        if m.group(1) != version:
            changed()
        return f'"{version}"  # <fcapi:sync-version>'

    for module in base.glob("__init__.py"):
        source = module.read_text()
        changed.reset()
        source = SYNC_VERSION_PATTERN_PY.sub(replacer, source)
        if changed:
            module.write_text(source)


def build_package(base: Path, pyproject: dict):
    project = pyproject.get("project")
    name = project.get("name")
    version = project.get("version")
    out = base / "dist"
    out.mkdir(parents=True, exist_ok=True)
    pkg = out / f"{name}-{version}.zip"
    excluded_files = pkg_excluded_files_re

    with zf.ZipFile(pkg, "w", zf.ZIP_DEFLATED) as file:
        for f in base.glob("**/*"):
            if not f.is_file():
                continue
            rel = f.relative_to(base)
            if excluded_files.match(str(rel)):
                continue
            file.write(f, rel)


def _lupdate(path: Path):
    from .tools import qt_tool_wrapper

    pyproject = parse_project_toml(path)
    patterns = ["**/*.py", "**/*.qml", "**/*.ui"]

    if lupdate_files := pyproject.freecad.lupdate_files:
        patterns.extend(lupdate_files)

    files = []
    excluded_files = pkg_excluded_files_re
    for pat in patterns:
        for f in path.glob(pat):
            rel = f.relative_to(path)
            if excluded_files.match(str(rel)):
                continue
            files.append(str(f) + "\n")

    module = next(scan_freecad_mods(path / "freecad"))
    languages = set(["en"])
    if langs := pyproject.freecad.lupdate_langs:
        for lang in langs:
            languages.add(lang.strip())

    out_dir = module / "resources" / "translations"
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", delete=False) as file_list:
        file_list.writelines(files)
        file_list.close()
        print(f"Translations {languages}")
        for lang in languages:
            ts = out_dir / f"{module.name}_{lang}.ts"
            qt_tool_wrapper(
                "lupdate",
                [
                    f"@{file_list.name}",
                    "-tr-function-alias",
                    "translate+=dtr",
                    "-noobsolete",
                    "-ts",
                    str(ts),
                ],
            )
            qt_tool_wrapper(
                "lrelease",
                [
                    str(ts),
                    "-qm",
                    str(ts.with_suffix(".qm")),
                ],
            )


@app.command()
def lupdate(path: Annotated[Path, typer.Argument(help="Project directory")] = os.getcwd()):
    """Generate translation files ts and qm."""
    _lupdate(path)


@app.command()
def build(path: Annotated[Path, typer.Argument(help="Project directory")] = os.getcwd()):
    """Build a zip distribution of the project in dist/"""
    pyproject = parse_project_toml(path)
    base = path / "freecad"

    print("Updating version in python files")
    for mod in scan_freecad_mods(base):
        update_version_py(mod, pyproject.project.version)

    print("Updating package.xml")
    package.update_package(path, pyproject)

    print("Updating translations")
    _lupdate(path)

    print("Building Addon distribution")
    build_package(path, pyproject)

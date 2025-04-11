# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

from pathlib import Path
from typing import Any, Iterator
import toml
from .utils import DictObject
import typer
from .console import print

def map_ident(key: str) -> Iterator[str]:
    return (k.replace("_", "-") for k in key.split("."))

class FreecadTool:
    icon: str
    freecad_min: str
    freecad_max: str
    lupdate_files: list[str]
    lupdate_langs: list[str]
    addon_dependencies: list[str]
    internal_dependencies: list[str]
    branch: str

class Project:
    name: str
    version: str
    description: str
    readme: str
    requires_python: str
    license: str
    maintainers: list[DictObject]
    authors: list[DictObject]
    keywords: list[str]
    urls: dict[str, str]
    dependencies: list[str]
    optional_dependencies: dict[str, list[str]]
    dependency_groups: DictObject

class PyProject(DictObject):
    project: Project
    tool: DictObject
    freecad: FreecadTool

    def __init__(self, path: Path):
        super().__init__(toml.load(path), map_ident)
        self.freecad = self.tool.freecad


def parse_project_toml(path: Path) -> PyProject:
    file = path / "pyproject.toml"

    if not file.exists():
        print("[red]pyproject.toml not found.")
        typer.Exit(2)

    pyproject = PyProject(file)

    if not pyproject.project.version:
        print("[red]project.version not available in pyproject.toml")
        typer.Exit(3)

    return pyproject

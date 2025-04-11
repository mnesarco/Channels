# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

from __future__ import annotations

import datetime
import re
import xml.etree.ElementTree as ET
from dataclasses import InitVar, asdict, dataclass
from functools import total_ordering
from pathlib import Path


from . import xml
from .project import PyProject
from packaging.requirements import Requirement


# Pattern to extract minimum python version from project.requires-python
MIN_VER_RULE_PATTERN = re.compile(r">?=?\s*(.*)")


@total_ordering
@dataclass(eq=False)
class XmlDepend:
    """
    package.xml <depend> element
    """

    text: InitVar[str]
    version_lt: str | None = None
    version_lte: str | None = None
    version_eq: str | None = None
    version_gte: str | None = None
    version_gt: str | None = None
    condition: str | None = None
    optional: str | None = None
    type: str | None = None

    def __post_init__(self, text):
        self._text = text

    @classmethod
    def from_xml(self, node: ET.Element) -> XmlDepend:
        return XmlDepend(node.text.strip(), **node.attrib)

    @classmethod
    def from_str(
        self, expr: str, optional: bool = False, type_: str | None = None
    ) -> XmlDepend | None:
        dep = Requirement(expr)
        attrs = {}
        for spec in dep.specifier:
            match spec.operator:
                case "<":
                    attrs["version_lt"] = spec.version
                case "<=":
                    attrs["version_lte"] = spec.version
                case "==":
                    attrs["version_eq"] = spec.version
                case ">=":
                    attrs["version_gte"] = spec.version
                case ">":
                    attrs["version_gt"] = spec.version
        if optional:
            attrs["optional"] = "true"
        if type_:
            attrs["type"] = type_
        return XmlDepend(dep.name, **attrs)

    def __hash__(self):
        return hash(self._text)

    def __eq__(self, value) -> bool:
        return value._text == self._text

    def xml(self) -> ET.Element:
        attrs = {k: v for k, v in asdict(self).items() if v}
        e = ET.Element("depend", attrs)
        e.text = self._text
        return e

    def __lt__(self, other):
        return self._text < other._text


def update_devs(devs: list[dict], tag: str, root: ET.Element):
    out = set()
    remove = []
    for m in root.iterfind(f"./{tag}"):
        text = m.text
        email = m.get("email", "")
        out.add((text.strip(), email.strip()))
        remove.append(m)
    for m in remove:
        root.remove(m)
    for a in devs:
        text = a.get("name")
        email = a.get("email", "")
        out.add((text.strip(), email.strip()))
    for name, email in sorted(out):
        xml.add_element(root, tag, name, email=email)


def update_tags(tags: list[str], root: ET.Element):
    out = set()
    remove = []
    for m in root.iterfind("./tag"):
        out.add(m.text.strip())
        remove.append(m)
    for m in remove:
        root.remove(m)
    for a in tags:
        out.add(a.strip())
    for a in sorted(out):
        xml.add_element(root, "tag", a)


def update_deps(deps: list[str], optional: bool, type_: str, node: ET.Element):
    out: set[XmlDepend] = set()
    remove = []
    for dep in deps:
        out.add(XmlDepend.from_str(dep, optional, type_))
    for dep in node.iterfind("./depend"):
        out.add(XmlDepend.from_xml(dep))
        remove.append(dep)
    for dep in remove:
        node.remove(dep)
    for dep in sorted(out):
        node.append(dep.xml())


def update_urls(urls: dict[str, str], node: ET.Element):
    out: set[tuple[str, str, str]] = set()
    remove = []
    for name, url in urls.items():
        out.add((name.lower().strip(), url.strip(), ""))
    for url in node.iterfind("./url"):
        out.add((url.get("type", "").strip(), url.text.strip(), ""))
        remove.append(url)
    for url in remove:
        node.remove(url)
    for name, url, branch in sorted(out):
        xml.add_element(node, "url", url, type=name, branch=branch)


def update_license(path: Path, node: ET.Element, license: str):
    xml.update_elem_text(node, "./license", license, create=True)
    for f in path.iterdir():
        if f.is_file() and f.name.lower().startswith("license"):
            node.find("license").set("file", f.name)
            break


def update_package(base: Path, pyproject: PyProject):
    file = base / "package.xml"

    if file.exists():
        tree = ET.parse(file)
        root = tree.getroot()
    else:
        root = ET.Element("package", format="1")
        # root.set("xmlns", "https://wiki.freecad.org/Package_Metadata")
        tree = ET.ElementTree(root)

    project = pyproject.project

    if name := project.name:
        xml.update_elem_text(root, "./name", name, create=True)

    if description := project.description:
        xml.update_elem_text(root, "./description", description, create=True)

    if version := project.version:
        xml.update_elem_text(root, "./version", version, create=True)

    if license := project.license:
        update_license(base, root, license)
        # xml.update_elem_text(root, "./license", license, create=True)

    date = datetime.date.isoformat(datetime.date.today())
    xml.update_elem_text(root, "./date", date, create=True)

    if maintainers := project.maintainers:
        update_devs(maintainers, "maintainer", root)

    if authors := project.authors:
        update_devs(authors, "author", root)

    if keywords := project.keywords:
        update_tags(keywords, root)

    if min_py_ver := project.requires_python:
        if m := MIN_VER_RULE_PATTERN.findall(min_py_ver):
            xml.update_elem_text(root, "./pythonmin", m[0], create=True)

    if deps := project.dependencies:
        update_deps(deps, optional=False, type_="python", node=root)

    if opt_deps := project.optional_dependencies:
        for deps in opt_deps.values():
            update_deps(deps, optional=True, type_="python", node=root)

    if urls := project.urls:
        update_urls(urls, node=root)

    if freecad := pyproject.freecad:
        if icon := freecad.icon:
            xml.update_elem_text(root, "./icon", icon, create=True)

        if v := freecad.freecad_min:
            xml.update_elem_text(root, "./freecadmin", v, create=True)

        if v := freecad.freecad_max:
            xml.update_elem_text(root, "./freecadmax", v, create=True)

        if deps := freecad.addon_dependencies:
            update_deps(deps, optional=False, type_="addon", node=root)

        if deps := freecad.internal_dependencies:
            update_deps(deps, optional=False, type_="internal", node=root)

        set_repository_branch(root, freecad.branch or "master")

    ET.indent(root, " " * 4, 0)
    tree.write(file, encoding="utf-8")


def set_repository_branch(root: ET.Element, branch: str):
    for child in root.iterfind("./url"):
        if child.get("type", "").lower() == "repository":
            child.set("branch", branch)

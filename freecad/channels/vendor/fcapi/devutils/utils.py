# SPDX-License: LGPL-3.0-or-later
# (c) 2025 Frank David Martínez Muñoz. <mnesarco at gmail.com>

import re
from typing import Any, Callable, Iterator
import operator

IDENTIFIER_RE = re.compile(r"[^\w]")

NOT_FOUND = object()


class BoolFlag:
    def __init__(self):
        self.changed = False

    def reset(self):
        self.changed = False

    def __call__(self):
        self.changed = True

    def __bool__(self):
        return self.changed


KeySplitter = Callable[[str], Iterator[str]]


def split_dot(key: str) -> list[str]:
    return key.split(".")


def split_ident(key: str) -> Iterator[str]:
    for part in key.split("."):
        yield IDENTIFIER_RE.sub("_", part)


def _dict_get(d: dict, path: str, sep: KeySplitter = split_dot, default=None):
    """Finds a value recursively in d"""
    value = default
    for p in sep(path):
        value = d.get(p, NOT_FOUND)
        if value is NOT_FOUND:
            return default
        if isinstance(value, dict):
            d = value
    return value


class DictStruct:
    def __init__(self, data: dict, sep: KeySplitter):
        self._data = data
        self._sep = sep

    def __getitem__(self, key):
        return self.get(key)

    def get(self, key: str, default=None):
        value = _dict_get(self._data, key, self._sep, NOT_FOUND)
        if value is NOT_FOUND:
            return default
        if isinstance(value, dict):
            return DictStruct(value, sep=self._sep)
        return value

    def items(self) -> Iterator[tuple[str, Any]]:
        for key, d in self._data.items():
            if isinstance(d, dict):
                yield key, DictStruct(d, self._sep)
            else:
                yield key, d

    def keys(self) -> Iterator[str]:
        get = operator.itemgetter(0)
        return (get(t) for t in self.items())

    def values(self) -> Iterator[Any]:
        get = operator.itemgetter(1)
        return (get(t) for t in self.items())

    def __contains__(self, key):
        return _dict_get(self._data, key, self._sep, NOT_FOUND) is NOT_FOUND

    def __bool__(self) -> bool:
        return bool(self._data)

    def __iter__(self):
        return self.keys()

    def __str__(self) -> str:
        return self._data.__str__()


class DictObject(DictStruct):
    def __init__(self, data, sep=split_dot):
        super().__init__(data, sep)
        self._cache = {}

    def get(self, name, default=None):
        if (cached := self._cache.get(name, NOT_FOUND)) is not NOT_FOUND:
            return cached
        value = super().get(name, NOT_FOUND)
        if value is NOT_FOUND:
            value = default
        elif isinstance(value, DictStruct):
            value = DictObject(value._data, self._sep)
        self._cache[name] = value
        return value

    def __getattr__(self, name):
        value = self.get(name, NOT_FOUND)
        if value is NOT_FOUND:
            return DictObject({}, self._sep)
        if isinstance(value, DictStruct):
            return DictObject(value, self._sep)
        return value

    def items(self):
        for k, v in super().items():
            if isinstance(v, DictStruct):
                yield k, DictObject(v._data, self._sep)
            else:
                yield k, v

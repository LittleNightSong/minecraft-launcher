import contextlib
import dataclasses
import random
import re
import string
import typing
import urllib.parse
from math import inf
from pathlib import Path
from typing import Literal, Any, Callable

import hydrogenlib.core
import yaml
from furl import furl
from hydrogenlib.core import getitems
from typeguard import check_type


class Visited(hydrogenlib.core.Visited):
    def raise_for_existence(self, v):
        if self[v]:
            raise KeyError(v)

    def record(self, v, raise_for_existence=True):
        if raise_for_existence:
            self.raise_for_existence(v)

        self[v] = True


class CustomTemplate(string.Template):
    idpattern = r'(?a:[a-zA-Z0-9_]+)'


def slots(cls):
    return dataclasses.dataclass(cls, slots=True)


class Pair:
    __slots__ = ['key', 'value']

    def __init__(self, k, v):
        self.key = k
        self.value = v

    def __str__(self):
        return f'{self.__class__.__name__}({self.key!r}, {self.value!r})'

    __repr__ = __str__

    def __getitem__(self, item):
        if item != self.key:
            raise KeyError(item)
        return self.value

    def __iter__(self):
        yield self.key
        yield self.value

    @classmethod
    def from_dict(cls, d):
        if len(d) == 1:
            k, v = next(iter(d.items()))
            return cls(k, v)
        else:
            raise ValueError(d)


@slots
class BaseRule:
    name: str
    args: dict


@slots
class TagRule:
    type: Literal[
        'host', 'protocol', 'prefix', 'suffix', 'path',
        'path-prefix', 'path-suffix', 'host-keyword', 'host-re-keyword', 'regular'
    ]
    value: str

    def match(self, url):
        info = urllib.parse.urlparse(url)
        return (
                self.type == 'host' and info.hostname == self.value
        ) or (
                self.type == 'protocol' and info.scheme == self.value
        ) or (
                self.type == 'prefix' and str(url).startswith(self.value)
        ) or (
                self.type == 'suffix' and str(url).endswith(self.value)
        ) or (
                self.type == 'path' and info.path == self.value
        ) or (
                self.type == 'path-prefix' and Path(info.path).is_relative_to(self.value)
        ) or (
                self.type == 'path-suffix' and
                Path(str(reversed(info.path))).is_relative_to(
                    str(reversed(self.value))
                )
        ) or (
                self.type == 'host-keyword' and self.value in info.hostname
        ) or (
                self.type == 'host-re-keyword' and re.search(self.value, info.hostname)
        ) or (
                self.type == 'regular' and re.fullmatch(self.value, str(url))
        ) or self.error()

    def error(self):
        raise ValueError(f'Unknown tag rule {self.type}')


@slots
class Tag:
    name: str
    rules: list[TagRule]

    def match(self, url):
        return any(
            rule.match(url) for rule in self.rules
        )


@slots
class MirrorRule:
    method: str
    tags: set[str]
    args: dict[str, Any]

    def match(self, tag):
        return tag in self.tags

    def match_multi(self, tags):
        tags = set(tags)
        return bool(self.tags & tags)

    def apply(self, url):
        f = furl(url)
        match self.method:
            case 'replace':
                old, new = getitems(self.args, 'old', 'new')
                return str(url).replace(old, new)
            case 're-host':
                old, new = getitems(self.args, 'old', 'new')
                if f.host == old:
                    f.host = new
                return f.url
            case _:
                raise ValueError(f'Unknown mirror rule {self.method}')


@slots
class Mirror:
    name: str
    rules: list[MirrorRule]

    def apply(self, url, tags):
        for rule in self.rules:
            if rule.match_multi(tags):
                return rule.apply(url)
        return None

    def match(self, tags) -> MirrorRule | None:
        for rule in self.rules:
            if rule.match_multi(tags):
                return rule

        return None


@slots
class _Task:
    done: Callable[[], None]

    if typing.TYPE_CHECKING:
        def done(self):
            ...


class Router:
    def __init__(self):
        self.tags = []
        self.methods = {}
        self.mirrors = {}

        self.v_tags = Visited()
        self.v_methods = Visited()
        self.v_mirrors = Visited()

        self.mirrors_load = {}

    def load_source(self, filename):
        with open(filename) as f:
            data = yaml.safe_load(f)
            # 1. 附加 tag 规则
            new_tags = []
            new_methods = {}
            new_mirrors = {}

            for name, rules in data['tags'].items():
                self.v_tags.record(name)
                new_tags.append(Tag(
                    nane=name,
                    rules=[
                        TagRule(*Pair.from_dict(rule)) for rule in rules
                    ]
                ))
            # 2. 附加方法
            for method, desc in data['methods'].items():
                self.v_methods.record(method)
                new_methods[method] = desc
                m_tags = desc['tags'] = set(desc.get('tags', []))

                # 应用标签
                for tag in self.tags:
                    if tag.apply(desc['url']):
                        m_tags.add(tag)

            # 3. 加载镜像
            for name, rules in data['mirrors'].items():
                self.v_mirrors.record(name)
                mirror = new_mirrors[name] = Mirror('', [])
                for rule in rules:
                    name, value = Pair.from_dict(rule)
                    if name == 'priority':
                        mirror.priority = check_type(value, int | float)
                    mirror.rules.append(MirrorRule(
                        name, tags=set(value.pop('tags', [])), args=value
                    ))

            self.tags.extend(new_tags)
            self.methods.update(new_methods)
            self.mirrors.update(new_mirrors)

    def get_url_tags(self, url):
        tags = set()
        for tag in self.tags:
            if tag.apply(url):
                tags.add(tag.name)

        return tags

    def route_url(self, url, mirror_priority=1):
        tags = self.get_url_tags(url)
        if mirror_priority == 1 or random.random() < mirror_priority:
            return any(
                mirror.apply(url, tags) for mirror in self.mirrors.values()
            )
        return url

    def mirror_load(self, mirror_name):
        return self.mirrors_load.get(mirror_name, 0)

    @contextlib.contextmanager
    def route(self, url, mirror_priority=1):
        tags = self.get_url_tags(url)
        min_load_rule: MirrorRule | None = None
        min_load_mirror_name: str | None = None
        min_load: float | int = inf
        if mirror_priority == 1 or random.random() < mirror_priority:
            for mirror in self.mirrors.values():
                if rule := mirror.apply(tags):
                    if min_load_rule is None or self.mirror_load(min_load_mirror_name) < min_load:
                        min_load_rule, min_load_mirror_name = rule, mirror.name
            return min_load_rule.apply(url)
        else:
            return url

    @contextlib.contextmanager
    def call(self, func_name, *args, **kwargs):
        def get_arg(key):
            if isinstance(key, int):
                return args[key]
            else:
                return kwargs[key]


if __name__ == '__main__':
    from rich.console import Console

    console = Console(width=150)
    console.print(
        yaml.safe_load(Path("../sources/minecraft.yaml").read_text())
    )

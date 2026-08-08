import dataclasses
import re
import string
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

import yaml
from yarl import URL

inf = float('inf')


def to_pair(dct: dict):
    assert isinstance(dct, dict) and len(dct) == 1, str(dct)
    return dct.copy().popitem()


@dataclass
class TagRule:
    method: str
    args: Any

    @property
    def value(self):
        return self.args['value']

    def match(self, url: str) -> bool:
        try:
            k = URL(url)
            return (
                    self.method == 'host' and k.host == self.value
            ) or (
                    self.method == 'protocol' and k.scheme == self.value
            ) or (
                    self.method == 'prefix' and url.startswith(self.value)
            ) or (
                    self.method == 'suffix' and url.endswith(self.value)
            ) or (
                    self.method == 'path' and k.path == self.value
            ) or (
                    self.method == 'path-prefix' and str(k.path).startswith(self.value)
            ) or (
                    self.method == 'path-suffix' and str(k.path).endswith(self.value)
            ) or (
                    self.method == 'host-keyword' and (self.value in k.host if k.host else False)
            ) or (
                    self.method == 'host-pattern' and bool(re.search(self.value, k.host) if k.host else 0)
            ) or (
                    self.method == 'port' and self.value == k.port
            ) or (
                    self.method == 'port-range' and k.port in range(*map(int, self.value.split('-')))
            ) or (
                    self.method == 'pattern' and bool(re.fullmatch(self.value, url))
            )
        except ValueError:
            return False


@dataclass
class Tag:
    name: str
    rules: list[TagRule]

    def match(self, url: str):
        return any(
            rule.match(url) for rule in self.rules
        )


@dataclass
class MirrorRule:
    method: str
    args: dict

    @property
    def tags(self):
        return self.args['tags']

    def apply(self, url: str, tags: set[str], mirror: Mirror) -> str:
        match self.method:
            case 'mapping':
                base_url = URL(mirror['url'])

                mapped_tags = set(self.args.keys())

                final_tags = mapped_tags & tags
                assert len(final_tags) == 1

                tag = final_tags.pop()

                path: str
                if path := self.args.get(tag):
                    return str(base_url / path.lstrip('/') / urlparse(url).path.lstrip('/'))
                # else:
                # return None
            # case ''  # TODO: More rules
        return None


@dataclass
class Mirror:
    name: str
    rules: list[MirrorRule]
    info: dict[str, Any]

    def apply(self, url: str, tags: set[str]) -> str | None:
        for rule in self.rules:
            if result := rule.apply(url, tags, self):
                return result

        return None

    def __getitem__(self, item):
        return self.info[item]


@dataclass
class Method:
    name: str
    url: str
    tags: set[str] = dataclasses.field(default_factory=set)
    defaults: dict[str, str] = dataclasses.field(default_factory=dict)
    template: string.Template = None

    def __post_init__(self):
        self.template = string.Template(self.url)
        if not self.template.is_valid():
            raise ValueError("Invalid template {!r}".format(self.url))

    def format(self, *args, **kwargs):
        defaults = self.defaults.copy()
        defaults.update(kwargs)

        kwargs = defaults

        for i, v in enumerate(args):
            kwargs.setdefault(str(i), v)

        # 提前检查所有的参数
        if len(kwargs) != len(self.args):
            expect_args = set(self.args)
            real_args = set(kwargs.keys())

            missing_args = expect_args - real_args
            extract_args = real_args - expect_args

            if missing_args and extract_args:
                raise TypeError(
                    f'function {self.name} got '
                    f'{len(extract_args)} unexpect args: {", ".join(extract_args)} '
                    f'and missing {len(missing_args)} args: {", ".join(missing_args)}'
                )
            elif missing_args:
                raise TypeError(
                    f'function {self.name} missing {len(missing_args)} args: {", ".join(missing_args)}'
                )
            else:
                raise TypeError(
                    f'function {self.name} got {len(extract_args)} unexpect args: {", ".join(extract_args)}'
                )

        return self.template.substitute(kwargs)

    @property
    def args(self):
        return self.template.get_identifiers()


@dataclass
class Namespace:
    name: str

    tags: list[Tag] = dataclasses.field(default_factory=list)
    methods: dict[str, Method] = dataclasses.field(default_factory=dict)
    mirrors: dict[str, Mirror] = dataclasses.field(default_factory=dict)

    load_mro: dict[str, int] = dataclasses.field(default_factory=dict)

    vis_tags: set[str] = dataclasses.field(default_factory=set)

    def exists(self, name, type: Literal['tags', 'methods', 'mirrors'] = 'tags'):
        match type:
            case 'tags':
                return name in self.vis_tags
            case 'methods':
                return name in self.methods
            case 'mirrors':
                return name in self.mirrors
            case _:
                raise TypeError(f'Unknown type {type}')

    def get_url_tags(self, url: str):
        return {tag.name for tag in self.tags if tag.match(url)}

    def has_method(self, name):
        return name in self.methods

    def route(self, url):
        tags = set(self.get_url_tags(url))
        # for mirror in self.mirrors.values():
        #     if result := mirror.apply(url, tags):
        #         return result
        matches = filter(
            lambda x: x[1],
            [
                (name, mirror.apply(url, tags))
                for name, mirror in self.mirrors.items()
            ]
        )
        # 找到负载最小的源
        min_load = inf
        for name, result in matches:
            load = self.load_mro.get(name, inf)
            if load < min_load:
                min_load = load
                url = result

        return url

    @contextmanager
    def call(self, name, *args, **kwargs):
        if not self.has_method(name):
            raise ValueError(f"不存在的源方法 {name}")
        try:
            self.load_mro.setdefault(name, 0)
            self.load_mro[name] += 1

            yield self.methods[name].format(*args, **kwargs)
        finally:
            self.load_mro[name] -= 1


class Router:
    def __init__(self):
        self.namespaces = {}  # type: dict[str, Namespace]

    def load_source(self, filename):
        with open(filename) as f:
            data = yaml.safe_load(f)
            # meta: 获取元数据
            meta = data['meta']

            namespace_name = meta['namespace']
            if namespace_name not in self.namespaces:
                self.namespaces[namespace_name] = Namespace(
                    namespace_name
                )

            np = self.namespaces[namespace_name]

            new_tags = np.tags
            new_methods = np.methods
            new_mirrors = np.mirrors

            # 1. 附加 tag 规则
            for tag in data['tags']:
                name = tag.pop('name')

                if np.exists(name, type='tags'):
                    raise ValueError(f'Tag {name} already exists')

                np.vis_tags.add(name)

                new_tags.append(Tag(
                    name=name,
                    rules=[
                        TagRule(rule.pop('method'), rule) for rule in tag.get('rules', [])
                    ]
                ))

            # 2. 附加方法
            for method in data['methods']:
                name = method.pop('name')

                if np.exists(name, type='methods'):
                    raise ValueError(f'Method {name} already exists')

                method_tags = set(method.get('tags', ()))

                # 应用标签
                for tag in np.tags:
                    if tag.match(method['url']):
                        method_tags.add(tag.name)

                new_methods[name] = Method(name, method['url'], method_tags)

            # 3. 加载镜像
            for mirror in data['mirrors']:
                name = mirror.pop('name')
                rules = mirror.pop('rules', [])

                if np.exists(name, type='mirrors'):
                    raise ValueError(f'Mirror {name} already exists')

                mirror = new_mirrors[name] = Mirror(name, [], mirror)
                for rule in rules:
                    method = rule.pop('method')

                    mirror.rules.append(MirrorRule(
                        method, rule
                    ))

    def namespace(self, name) -> Namespace:
        return self.namespaces[name]

    def get_url_tags(self, url: str, namespace: str):
        return self.namespaces[namespace].get_url_tags(url)

    def apply(self, url: str, namespace: str):
        tags = set(self.get_url_tags(url, namespace))
        for mirror in self.namespaces[namespace].mirrors.values():
            if result := mirror.apply(url, tags):
                return result
        return url


if __name__ == '__main__':
    router = Router()
    router.load_source(
        r"E:\.projects\minecraft-launcher\app\core\router\rules\minecraft.yaml")
    import rich

    rich.print(router.namespaces)
    print(router.apply("https://resources.download.minecraft.net/ab/absjdfldsjlfjsldjflksjd", "minecraft-resources"))
    minecraft = router.namespaces['minecraft-resources']
    with minecraft.call("get-asset", hash='asldkjflaksjdf', hash_prefix='as') as url:
        print(url)


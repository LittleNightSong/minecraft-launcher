import string
from typing import Iterable, Any, Mapping


def getattr_path(obj, path: Iterable[str], /) -> Any:
    for i in path:
        obj = getattr(obj, i)
    return obj


class EnhancedTemplate(string.Template):
    idpattern = r'([_a-z][_a-z0-9.]*[_a-z0-9])'

    def __init__(self, template: str):
        super().__init__(template)

    def substitute(self, mapping=None, /, **kwds: object) -> str:
        data = mapping or kwds
        real_data = {}
        for i in self.get_identifiers():
            path = i.split('.')
            obj = data[path[0]]
            value = getattr_path(obj, path[1:])
            real_data[i] = value

        return super().substitute(real_data)

    def safe_substitute(self, mapping: Mapping[str, object] = {}, /, **kwds: object) -> str:
        data = mapping or kwds
        real_data = {}
        for i in self.get_identifiers():
            path = i.split('.')
            try:
                obj = data[path[0]]
                value = getattr_path(obj, path[1:])
                real_data[i] = value
            except AttributeError, KeyError:
                pass

        return super().safe_substitute(real_data)
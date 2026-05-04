from pathlib import Path

import orjson


class InstanceDirectory:
    __slots__ = ['path', '_desc']

    def __init__(self, path):
        self.path = Path(path)
        self._desc = None

    @property
    def desc(self):
        if self._desc is None:
            self._desc = orjson.loads(Path(self.desc_file).read_bytes())

        return self._desc
    desc_file: Path = property(lambda self: Path(self.path / (self.path.name + '.json')))
    main_file: Path = property(lambda self: self.path / (self.path.name + '.jar'))
    id: str = property(lambda self: self.desc['id'])
    main_class: str = property(lambda self: self.desc['mainClass'])
    name: str = property(lambda self: self.path.name)

    def ensure_exists(self):
        self.path.mkdir(parents=True, exist_ok=True)

    def check(self):
        return (self.path / (self.path.name + '.json')).exists()



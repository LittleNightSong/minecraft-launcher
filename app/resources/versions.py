from pathlib import Path

from app.resources.instance import InstanceDirectory


class VersionsDirectory:
    def __init__(self, path):
        self.path = Path(path)

    def instance(self, name):
        return InstanceDirectory(self.path / name)

    def exists(self, name):
        return (self.path / name).is_dir()

    def instances(self) -> list[InstanceDirectory]:
        return list(
            map(lambda x: InstanceDirectory(x),
                filter(
                    lambda x: x.is_dir() and InstanceDirectory(x).check(),
                    self.path.iterdir()
                )))

    @property
    def mapping(self) -> dict[str, list[InstanceDirectory]]:
        mapping = {}
        for ins in self:
            if ins.check():
                mapping.setdefault(ins.id, [])
                mapping[ins.id].append(ins)
        return mapping

    def __iter__(self):
        return iter(self.instances())
from pathlib import Path
from typing import Iterable

from app.core.minecraft.directories import InstanceDirectory
from .base import BaseDirectory
from app.core.common import InvaildInstance


class VersionsDirectory(BaseDirectory):
    def __init__(self, path):
        self.path = Path(path)

    def instance(self, name, validate: bool = False) -> InstanceDirectory:
        ins = InstanceDirectory(self.path / name)
        if validate and not ins.is_valid():
            raise InvaildInstance(name)

        return ins

    def exists(self, name, validate: bool = True) -> bool:
        if validate:
            return self.instance(name).is_valid()
        else:
            return (self.path / name).is_dir()

    def instances(self, skip_broken=True) -> list[InstanceDirectory]:
        return list(
            map(
                lambda x: InstanceDirectory(x),
                filter(
                    lambda x: x.is_dir() and (not skip_broken or InstanceDirectory(x).is_valid()),
                    self.path.iterdir()
                )
            )
        )

    def select(self, names: Iterable[str], validate: bool = False):
        return [self.instance(name, validate=validate) for name in names]

    @property
    def mapping(self) -> dict[str, list[InstanceDirectory]]:
        mapping = {}
        for ins in self:
            if ins.is_valid():
                mapping.setdefault(ins.id, [])
                mapping[ins.id].append(ins)
        return mapping


    def __iter__(self):
        return iter(self.instances())

    def __contains__(self, item):
        return self.exists(str(item))

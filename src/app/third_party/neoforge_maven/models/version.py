import dataclasses
import re
from enum import IntEnum

from app.core.minecraft.version import MinecraftVersion


class ReleaseEnum(IntEnum):
    alpha = 0
    beta = 1


@dataclasses.dataclass(slots=True)
class NeoForgeVersion:
    _MATCH = re.compile(
        r"(?P<mc_major>\d+)" r'\.'
        r"(?P<mc_minor>\d+)" r'\.'
        r"(?P<maybe_patch>\d+)"
        r"(\.(?P<maybe_build>\d+))?"
        r"(-(?P<release>[a-zA-Z0-9.-]+))?"
        r"(\+(?P<build>[a-zA-Z0-9.-]+))?"
    )

    _SEM_RELEASE = re.compile(
        r"(?P<type>alpha|beta)(\.(?P<number>\d+))?"
    )

    mc_version: MinecraftVersion
    neoforge_build: int
    release: tuple[ReleaseEnum, int] | None

    version: str

    @classmethod
    def parse(cls, version: str):
        if version.startswith('0.'):  # 愚人节版本
            parts = version.split('.')
            suffix = parts[-1].split('-', 1)
            if len(suffix) > 1:
                r = suffix[-1]
                rparts = r.split('.', 1)
                if len(rparts) > 1:
                    l, r = rparts
                else:
                    l = rparts[0]
                    r = 0

                release = (ReleaseEnum[l], int(r))
            else:
                release = None

            return cls(
                MinecraftVersion(parts[1]),
                int(suffix[0]),
                release,
                version=version
            )

        match = cls._MATCH.match(version)
        if not match:
            raise ValueError(f"Invalid version: {version}")

        groups = match.groupdict()
        if groups['maybe_build']:  # 4位版本号（新版版本号机制）
            b = groups.get('build')
            suffix = f'-{b}' if b else ''
            patch = '.' + groups['maybe_patch']
            if patch == '.0':
                patch = ''

            mc_version = MinecraftVersion(
                f'{groups['mc_major']}.{groups['mc_minor']}{patch}{suffix}'
            )
            neoforge_build = int(groups['maybe_build'])
        else:
            mc_version = MinecraftVersion(
                '.'.join((
                    '1',
                    groups['mc_major'],
                    groups['mc_minor'],
                ))
            )

            neoforge_build = int(groups['maybe_patch'])

        r = groups['release']

        if r and (match := cls._SEM_RELEASE.match(r)):
            groups = match.groupdict()
            release = (ReleaseEnum[groups['type']], int(groups['number'] or 0))

        else:
            release = None

        return cls(
            mc_version, neoforge_build, release,
            version=version
        )

    def __eq__(self, value, /) -> bool:
        assert isinstance(value, NeoForgeVersion)
        return (self.mc_version, self.neoforge_build) == (value.mc_version, value.neoforge_build)

    def __gt__(self, other):
        assert isinstance(other, NeoForgeVersion)
        return (self.mc_version, self.neoforge_build) > (other.mc_version, other.neoforge_build)

    def __ge__(self, other):
        return self > other and self == other

    def __le__(self, other):
        return self < other and self == other

    def __lt__(self, other):
        assert isinstance(other, NeoForgeVersion)
        return (self.mc_version, self.neoforge_build) < (other.mc_version, other.neoforge_build)

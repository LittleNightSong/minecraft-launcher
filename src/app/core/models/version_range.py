import bisect
import re
from functools import lru_cache
from typing import Iterable, SupportsInt

import msgspec
import semver
from semver.version import Comparable


class Version(semver.Version): # todo: support api part
    __slots__ = ('_has_minor', '_has_patch', '_api')

    # Copy from `semver.Version`

    #: Regex for number in a prerelease
    _LAST_NUMBER = re.compile(r"(?:\D*(\d+)\D*)+")
    #: Regex template for a semver version
    _REGEX_TEMPLATE = r"""
                ^
                (?P<A>0|[1-9]\d*)
                (?:
                    \.
                    (?P<B>0|[1-9]\d*)
                )?
                (?:
                    \.
                    (?P<C>0|[1-9]\d*)
                )?
                (?:
                    \.
                    (?P<D>0|[1-9]\d*)
                )?
                (?:-(?P<prerelease>
                    (?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)
                    (?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*
                ))?
                (?:\+(?P<build>
                    [0-9a-zA-Z-]+
                    (?:\.[0-9a-zA-Z-]+)*
                ))?
                $
            """
    #: Regex for a semver version
    _REGEX = re.compile(
        _REGEX_TEMPLATE,
        re.VERBOSE,
    )

    @classmethod
    def parse(cls, version, optional_minor_and_patch: bool = False) -> Version:
        if isinstance(version, bytes):
            version = version.decode("UTF-8")
        elif not isinstance(version, str):  # type: ignore
            raise TypeError("not expecting type '%s'" % type(version))

        match = cls._REGEX.match(version)

        if match is None:
            raise ValueError(f"{version} is not valid SemVer string")

        mvp = match.groupdict()

        if mvp['D'] is None:  # 三元组版本号
            parts = {
                'major': mvp['A'],
                'minor': mvp['B'],
                'patch': mvp['C'],
                'prerelease': mvp['prerelease'],
                'build': mvp['build']
            }
        else:  # 四元组版本号
            parts = {
                'major': mvp['A'],
                'api': mvp['B'],
                'minor': mvp['C'],
                'patch': mvp['D'],
                'prerelease': mvp['prerelease'],
                'build': mvp['build']
            }

        return cls(**parts)

    def __init__(
            self,
            major,
            minor=None,
            patch=None,
            api: SupportsInt | None = None,
            prerelease=None,
            build=None,
    ):
        # Build a dictionary of the arguments except prerelease and build
        # version_parts = {"major": int(major), "minor": int(minor), "patch": int(patch)}
        #
        # for name, value in version_parts.items():
        #     if value < 0:
        #         raise ValueError(
        #             "{!r} is negative. A version can only be positive.".format(name)
        #         )

        self._has_minor = minor is not None
        self._has_patch = patch is not None

        self._major = int(major)
        self._minor = int(minor or 0)
        self._patch = int(patch or 0)

        if self._major < 0:
            raise ValueError(
                "'major' is negative. A version can only be positive."
            )
        if self._minor < 0:
            raise ValueError(
                "'minor' is negative. A version can only be positive."
            )
        if self._patch < 0:
            raise ValueError(
                "'patch' is negative. A version can only be positive."
            )

        self._api = api
        self._prerelease = None if prerelease is None else str(prerelease)
        self._build = None if build is None else str(build)

    @property
    def has_minor(self):
        return self._has_minor

    @property
    def has_patch(self):
        return self._has_patch

    @property
    def has_api(self) -> bool:
        return self._api is not None

    @property
    def is_quadruple(self):
        return self.has_api

    @property
    def is_triple(self):
        return not self.has_api

                


class Bound(msgspec.Struct, frozen=True):
    value: Version | None = None
    include: bool = False

    @classmethod
    def new(cls, value: str | Version | None, include: bool = False):
        if value is None:
            return cls(None, True)

        if not isinstance(value, Version):
            value = Version.parse(value, optional_minor_and_patch=True)
        return cls(value, include)


class VersionRange(msgspec.Struct, frozen=True):
    lbound: Bound
    rbound: Bound

    def is_vaild(self):
        if self.lbound.value is None or self.rbound.value is None:
            return True

        if self.lbound.value == self.rbound.value:
            if not self.lbound.include or not self.rbound.include:  # ">1.0 <=1.0" ==> !!!
                return False
            # else:  # ">=1.0 <=1.0" ==> 1.0
            return True
        elif self.lbound.value > self.rbound.value:  # ">1.2 <1.1" ==> !!!
            return False

        # else: ">1.2 <1.3" ==> Right
        return True

    def filter(self, versions: list[str | Version], sort=True):
        if self.lbound.value is None and self.rbound.value is None:
            return versions.copy()

        converted = map(lambda x: (x if isinstance(x, Version) else Version.parse(x)), versions)

        if sort:
            converted = sorted(converted)

        versions = list(converted)

        l_idx = 0
        r_idx = len(versions)

        # 2. 处理左边界
        if lv := self.lbound.value:
            if self.lbound.include:  # >= lv
                l_idx = bisect.bisect_left(versions, lv)
            else:  # > lv
                l_idx = bisect.bisect_right(versions, lv)

        # 3. 处理右边界
        if rv := self.rbound.value:
            if self.rbound.include:  # <= rv
                r_idx = bisect.bisect_right(versions, rv)
            else:  # < rv
                r_idx = bisect.bisect_left(versions, rv)

        return versions[l_idx:r_idx]

    @classmethod
    @lru_cache(maxsize=24)
    def parse(cls, spec: str):
        if spec.startswith(('(', '[')):
            strips = spec.split(',', 1)

            if len(strips) == 1:
                v = Version.parse(strips[0].strip()[1:-1])
                return cls(
                    Bound(
                        v,
                        True
                    ),
                    Bound(
                        v,
                        True
                    )
                )

            lpart, rpart = strips
            lpart = lpart.strip()[1:]
            rpart = rpart.strip()[:-1]

            if lpart:
                lbound = Bound(
                    Version.parse(lpart, optional_minor_and_patch=True),
                    spec[0] == '['
                )
            else:
                lbound = Bound()
            if rpart:
                rbound = Bound(
                    Version.parse(rpart, optional_minor_and_patch=True),
                    spec[-1] == ']'
                )
            else:
                rbound = Bound()

            return cls(lbound, rbound)

        elif spec.startswith(('>', '=' '<', '~', '^')):
            raw_parts = spec.split(' ')
            # 提取所有 part 的比较符片段
            parts = []
            for r in raw_parts:
                if not r:
                    continue

                if r[0] in '~^=':
                    parts.append((r[0], r[1:]))
                elif r[0] in '><':
                    if r[1] == '=':
                        parts.append((r[:2], r[2:]))
                    else:
                        parts.append((r[0], r[1:]))
                else:
                    raise ValueError(f'Invalid spec: {spec}')

            lbound = rbound = None
            for opt, value in parts:
                match opt:
                    case '>':
                        lbound = Bound.new(value, False)
                    case '<':
                        rbound = Bound.new(value, False)
                    case '>=':
                        lbound = Bound.new(value, True)
                    case '<=':
                        rbound = Bound.new(value, True)
                    case '=':
                        lbound = Bound.new(value, True)
                        rbound = Bound.new(value, True)
                    case '~':
                        ver = Version.parse(value, True)
                        lbound = Bound.new(ver, True)
                        if ver.has_minor:
                            rbound = Bound(
                                Version(
                                    ver.major, ver.minor + 1, ver.patch
                                ),
                                False
                            )
                        else:
                            rbound = Bound(
                                Version(
                                    ver.major + 1, 0, 0
                                ),
                                False
                            )

                    case '^':
                        ver = Version.parse(value, True)
                        lbound = Bound(
                            ver, True
                        )
                        rbound = Bound(
                            Version(ver.major + 1, 0, 0),
                            False
                        )

            if lbound is None:
                lbound = Bound()

            if rbound is None:
                rbound = Bound()

            return cls(lbound, rbound)

        else:
            v = Version.parse(spec, optional_minor_and_patch=True)
            return cls(
                Bound(
                    v, True
                ),
                Bound(
                    v,
                      True
                )
            )
            raise ValueError(f"{spec!r} Not a range")

    def __str__(self) -> str:
        l = '[' if self.lbound.include else '('
        r = ']' if self.rbound.include else ')'

        return f"{l}{self.lbound.value or '*'}, {self.rbound.value or '*'}{r}"


class Ranges:
    __slots__ = ('_ranges',)

    def __init__(self, ranges: Iterable[VersionRange]):
        self._ranges = tuple(ranges)

    @property
    def ranges(self) -> tuple[VersionRange, ...]:
        return self._ranges

    @classmethod
    def parse(cls, specs):
        return cls((
            VersionRange.parse(x) if not isinstance(x, VersionRange) else x
            for x in specs
        ))

    def filter(self, versions: list[str | Version], sort=False):
        converted = map(
            lambda x: x if isinstance(x, Version) else Version.parse(x, True),
            versions
        )
        if sort:
            converted = sorted(converted)

        versions = list(converted)

        for rng in self.ranges:
            versions = rng.filter(versions, sort=False)

        return versions


def parse(spec: str | list[str] | tuple[str, ...]):
    if isinstance(spec, str):
        return VersionRange.parse(spec)
    else:
        return Ranges.parse(spec)


def filter_versions(versions, spec: str | list[str] | tuple[str, ...], sort=False):
    spec = parse(spec)
    return spec.filter(versions, sort=sort)


def merge_two(r1: VersionRange, r2: VersionRange):
    lb = r1.lbound
    rb = r1.rbound

    rlb = r2.lbound
    rrb = r2.rbound

    if rlb.value is not None:
        if lb.value is None:
            lb = rlb
        elif rlb.value > lb.value:
            lb = rlb
        elif rlb.value == lb.value and not rlb.include:  # lb= <=1.0 rlb= <1.0
            lb = rlb
        # else: # 说明更宽松，不需要更新 lb

    if rrb.value is not None:
        if rb.value is None:
            rb = rrb
        elif rrb.value < rb.value:
            rb = rrb
        elif rrb.value == rb.value and not rrb.include:  # rb= >=1.0 rrb= >1.0
            rb = rrb
        # else: # 同理

    return VersionRange(lb, rb)


def merge(ranges: Iterable[str | VersionRange] | Ranges) -> VersionRange:
    if not isinstance(ranges, Ranges):
        ranges = Ranges.parse(ranges)

    lb = Bound(None)
    rb = Bound(None)
    for rng in ranges.ranges:
        rlb = rng.lbound
        rrb = rng.rbound
        if rlb.value is not None:
            if lb.value is None:
                lb = rlb
            elif rlb.value > lb.value:
                lb = rlb
            elif rlb.value == lb.value and not rlb.include:  # lb= <=1.0 rlb= <1.0
                lb = rlb
            # else: # 说明更宽松，不需要更新 lb

        if rrb.value is not None:
            if rb.value is None:
                rb = rrb
            elif rrb.value < rb.value:
                rb = rrb
            elif rrb.value == rb.value and not rrb.include:  # rb= >=1.0 rrb= >1.0
                rb = rrb

    return VersionRange(lb, rb)


if __name__ == '__main__':
    from rich import print

    versions = [
        '1.0.0',
        '1.0.1',
        '1.0.2',
        '1.1.0',
        '1.1.1',
        '1.1.2',
        '1.1.3',
        '1.1.4',
        '1.2.0',
        '1.2.1',
        '1.2.2',
        '1.3.0',
        '2.1.0',
        '2.1.1',
        '2.1.2',
        '2.1.3',
        '2.2.0',
        '2.2.1',
        '2.3.1',
    ]

    vrange = VersionRange.parse('[1.0, 1.2)')
    print(vrange)

    result = vrange.filter(versions)

    print(result)

import msgspec


class PackInfo(msgspec.Struct, kw_only=True, gc=False):
    pack_format: int | None = None  # 为兼容性保留的字段，实际已弃用
    description: str  # Text Component

    class SupportedFormatsStruct(msgspec.Struct, kw_only=True, gc=False):
        min_inclusive: int | None = None
        max_inclusive: int | None = None

    supported_formats: SupportedFormatsStruct | int | tuple[int, int] | None = None  # Old

    min_format: tuple[int, int] | None = None
    max_format: tuple[int, int] | None = None


class PackMeta(msgspec.Struct, kw_only=True, gc=False):
    pack: PackInfo

    def _check_compatible_old(self, p):
        support = self.pack.supported_formats

        if isinstance(support, int):
            return support == p

        elif isinstance(support, tuple):
            min, max = support
            return (
                    min <= p <= max
            )

        if (min := support.min_inclusive) and p < min:
            return False

        if (max := support.max_inclusive) and p > max:
            return False

        return True

    def _check_compatible(self, p):
        max = self.pack.max_format
        min = self.pack.min_format

        if max and p > max:
            return False

        if min and p < min:
            return False

        return True

    def is_compatible_with(self, pack_format: int | tuple[int, int]) -> bool:
        if self.pack.supported_formats:
            return self._check_compatible_old(pack_format)
        else:
            if isinstance(pack_format, int):
                pack_format = (pack_format, float('inf'))

            return self._check_compatible(pack_format)

import typing

import msgspec

BasicTypes = dict | set | list | tuple | int | float


class _Unifiable[T, **P](typing.Protocol):
    def unify(self, *args: P.args, **kwargs: P.kwargs) -> T:
        ...


def unify[R, **P](
        raw: BasicTypes,
        model: type[_Unifiable[R, P]],
        *args: P.args,
        **kwargs: P.kwargs
) -> R:
    if not isinstance(raw, BasicTypes):
        from_attributes = True
    else:
        from_attributes = False

    return msgspec.convert(
        raw,
        model,
        from_attributes=from_attributes
    ).unify(*args, **kwargs)


def subdict(dct, *keys):
    return {
        k: dct[k] for k in keys
    }

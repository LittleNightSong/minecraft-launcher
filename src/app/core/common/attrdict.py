class AttrDict(dict):
    def __getattr__(self, name):
        return self[name]


class DictObject:
    def __init__(self, attrs: dict):
        self.__dict__.update(attrs)


def as_object(dct: dict):
    return DictObject(dct)

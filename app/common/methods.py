import functools

import orjson


def as_async(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def read_json(file):
    with open(file, 'rb') as f:
        return orjson.loads(f.read())


def write_json(file, obj):
    with open(file, 'wb') as f:
        f.write(orjson.dumps(obj))


def xpath(obj, path):
    for part in path.split('/'):
        if not part:
            continue

        obj = obj[part]
    return obj


def dotpath(obj, path):
    # original_obj = obj
    # try:
    for part in path.split('.'):
        if not part:
            continue

        obj = obj[part]
    return obj


def listpath(obj, *path):
    for part in path:
        obj = obj[part]

    return obj

# except KeyError as e:
#     trace = []
#     error_key = e
#     obj = original_obj
#     try:
#         for part in path.split('.'):
#             if not part:
#                 continue
#
#             trace.append(obj)
#             obj = obj[part]
#     except KeyError as e:
#         pass
#
#     logger.error(
#         f"向对象{original_obj}请求 {path} 时出现问题:\n"
#         f"parts: {path.split('.')}\n"
#         f"trace: {trace}, error_key: {error_key}"
#     )

class Object:
    __slots__ = ['_dct']

    def __init__(self, dct):
        self._dct = dct

    def __getattr__(self, name):
        value = self._dct[name]
        if isinstance(value, dict):
            return Object(value)
        return value

    def __setattr__(self, key, value):
        if key in self.__slots__:
            super().__setattr__(key, value)
        self._dct[key] = value

    def __getitem__(self, item):
        return self._dct[item]

    def __setitem__(self, key, value):
        self._dct[key] = value

    def dotpath(self, path):
        return dotpath(self._dct, path)

    def xpath(self, path):
        return xpath(self._dct, path)

    def get(self, path, default=None, *, method='dot'):
        try:
            if method == 'dot':
                return dotpath(self._dct, path)
            elif method == 'xpath':
                return xpath(self._dct, path)
            else:
                raise NotImplementedError("method not supported")
        except KeyError:
            return default

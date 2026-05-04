import orjson


class Translator:
    def __init__(self):
        self.mapping = None

    def load(self, path):
        with open(path) as f:
            mapping = orjson.loads(f.read())
            # 检查映射表
            for k, v in mapping.items():
                if not (isinstance(k, str) and isinstance(v, str)):
                    raise RuntimeError('Invalid language file')

            self.mapping = mapping

    def tr(self, string, *args, **kwargs):
        return (self.mapping[string] if self.mapping else string).format(*args, **kwargs)

    def trs(self, *string):
        return tuple(self.tr(s) for s in string)


translator = Translator()
tr = translator.tr
trs = translator.trs

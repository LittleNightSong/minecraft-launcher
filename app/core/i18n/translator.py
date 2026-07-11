import msgspec


class Translator:
    def __init__(self):
        self.mapping = None

    def load(self, path):
        with open(path) as f:
            self.mapping = msgspec.json.decode(f.read(), type=dict[str, str])

    def tr(self, string, *args, **kwargs):
        return (self.mapping[string] if self.mapping else string).format(*args, **kwargs)

    def trs(self, *string):
        return tuple(self.tr(s) for s in string)


translator = Translator()
tr = translator.tr
trs = translator.trs

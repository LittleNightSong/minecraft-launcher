import json5
import msgspec
import rich.theme


def load_theme(file):
    with open(file) as f:
        styles = msgspec.convert(json5.load(f), type=dict[str, str])

    return rich.theme.Theme(styles)


def get_theme():
    return load_theme('./app/interfaces/commandline/assets/themes/theme.json5')

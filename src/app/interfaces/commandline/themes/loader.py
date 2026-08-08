import json5
import msgspec
import rich.theme
import importlib.resources as ir

def load_theme(text):
    styles = msgspec.convert(json5.loads(text), type=dict[str, str])
    return rich.theme.Theme(styles)


def get_theme():
    # return load_theme('./app/interfaces/commandline/assets/themes/theme.json5')
    return load_theme(
        ir.read_text('app.interfaces.commandline.assets.themes', 'theme.json5')
    )

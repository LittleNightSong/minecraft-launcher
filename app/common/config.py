from pathlib import Path

import platformdirs
from orjson import orjson

APP_NAME = "CLCL"

app_dir = platformdirs.PlatformDirs(APP_NAME, ensure_exists=True)

USER_CONFIG_DIR = Path(app_dir.user_config_dir)
USER_STATE_DIR = Path(app_dir.user_state_dir)

def load():
    config = {}

    # Load repos
    file = USER_CONFIG_DIR / "config.json"
    if file.exists():
        return orjson.loads(file.read_bytes())

    else:
        return {}


cfg = load()


def save():
    file = USER_CONFIG_DIR / "config.json"
    with file.open("w") as f:
        f.write(orjson.dumps(cfg))

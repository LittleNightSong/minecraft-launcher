from pathlib import Path


class LauncherDataDirectory:
    def __init__(self, path):
        self.path = Path(path)

    @property
    def cache_version_desc(self):
        return self.path / 'version_desc'

    def get_version_desc(self, id):
        p = self.cache_version_desc / (id + '.json')
        if p.exists():
            return p
        else:
            return None

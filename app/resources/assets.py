from pathlib import Path

from app.common import compute_hash


class AssetsDirectory:
    def __init__(self, path):
        self.path = Path(path)
        self.objects_dir.mkdir(exist_ok=True, parents=True)
        self.indexes_dir.mkdir(exist_ok=True, parents=True)

    @property
    def objects_dir(self):
        return self.path / 'objects'

    @property
    def indexes_dir(self):
        return self.path / 'indexes'

    def asset(self, hash) -> Path:
        return self.objects_dir / hash[:2] / hash

    def index_exists(self, index_id):
        return (self.indexes_dir / f'{index_id}.json').exists()

    def index_filename(self, index_id):
        return self.indexes_dir / f'{index_id}.json'

    async def check(self, hash, size=None):
        asset = self.asset(hash)
        if not asset.exists():
            return False

        if size is not None:
            if asset.stat().st_size != size:
                return False

        computed_hash = await compute_hash(asset)
        return computed_hash == hash

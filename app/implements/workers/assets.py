from app.core.common import FileInfo
from app.core.common.file_validator import FileValidator
from app.core.resources.assets import AssetsDirectory
from app.implements.workers.common_files import CommonFileChecker


class AssetsChecker(CommonFileChecker):
    def __init__(self, assets_dir: AssetsDirectory, validator: FileValidator | None = None):
        super().__init__(validator)

        self.assets_dir = assets_dir

    async def process_one(self, input):
        return await super().process_one([
            FileInfo(
                filename=self.assets_dir / hash,
                size=size,
                hash=hash,
                key=hash
            )
            for hash, size in input
        ])

from string import Template

from app.core.models import FileInfo
from app.core.file_validator import FileValidator
from app.core.minecraft.model_version_meta import StandardLibraryStruct
from app.core.minecraft.resources import LibrariesDirectory
from app.core.workers.common_files import CommonFileChecker


class LibrariesChecker(CommonFileChecker):
    def __init__(
            self,
            env,
            libs_dir: LibrariesDirectory,
            validator: FileValidator | None = None
    ):
        super().__init__(validator)

        self.env = env
        self.libs_dir = libs_dir
        self.visited_names = set()


    async def process_one(self, libraries: list[StandardLibraryStruct]):
        files: list[FileInfo] = []

        for lib in libraries:
            if lib.name not in self.visited_names:
                self.visited_names.add(lib.name)
            else:
                continue

            files.extend([
                FileInfo.from_downloads_struct(
                    downloads=dl,
                    filename=self.libs_dir.library_path(name),
                    meta=dl.path
                )
                for dl, name in lib.collect_files(env=self.env)
            ])

        await super().process_one(files)

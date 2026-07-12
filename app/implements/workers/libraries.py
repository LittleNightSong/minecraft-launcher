from string import Template

from app.core.common import FileInfo
from app.core.common.file_validator import FileValidator
from app.core.minecraft.model_version_meta import LibraryStruct
from app.core.resources.libraries import LibrariesDirectory
from app.implements.workers.common_files import CommonFileChecker


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

    async def process_one(self, libraries: list[LibraryStruct]):
        files: list[FileInfo] = []

        for lib in libraries:
            if lib.name not in self.visited_names:
                self.visited_names.add(lib.name)
            else:
                continue

            if lib.natives: # 如果包含本地库 jar
                classifier = Template(
                    lib.natives[self.env['os']]
                ).substitute(self.env)  # Fix for old minecraft versions

                download_info = lib.downloads.classifiers[classifier]

                files.append(FileInfo.from_downloads_struct(
                    downloads=download_info,
                    filename=self.libs_dir / download_info.path,
                    meta=download_info.path
                ))

            # 无论是不是本地库，artifact 这个通用的都要下载
            # 但是要注意某些旧版本的库可能不提供 artifact
            if artifact := lib.downloads.artifact:
                files.append(FileInfo.from_downloads_struct(
                    downloads=artifact,
                    filename=self.libs_dir / artifact.path,
                    meta=artifact.path
                ))

        await super().process_one(files)

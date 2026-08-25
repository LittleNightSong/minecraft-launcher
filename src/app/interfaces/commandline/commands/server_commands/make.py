import typer

from app.core.fetcher import Fetcher
from app.core.file_validator import FileValidator
from app.core.i18n import tr
from app.core.models import FileSpec
from app.core.models.methods import unify
from app.core.network import Session
from app.third_party.mojang import MinecraftAPI
from app.interfaces.commandline.base import Command, find_repository, console


class MakeCommand(Command):
    name = 'make'

    # noinspection attribute-outside-init
    async def init(self, repository):
        self.repository = find_repository(repository, abort=True)

        self.session = Session()
        self.model_cacher = self.repository.model_cacher
        self.file_cacher = self.repository.file_cacher

        self.api = MinecraftAPI(self.session)
        self.file_validator =  FileValidator()
        self.fetcher = Fetcher(
            self.session,
            model_cacher=self.model_cacher,
            file_cacher=self.file_cacher,
            file_validator=self.file_validator
        )

    async def main(
            self,
            version_id: str,
            name: str | None = None,
            repository: str | None = typer.Option(
                None,
                '--repository', '-r'
            )
    ):
        name = name or version_id
        repo = self.repository

        with console.status(tr("获取版本清单...")) as s:
            manifest = await self.fetcher.fetch_model(
                fetcher=self.api.fetch_version_manifest,
                type=self.api.models.VersionManifestModel,
                key='versionmeta:manifest',
                ttl=3600,
            )

            entry = manifest.find(id=version_id)
            if not entry:
                console.error(tr("指定名称的版本不存在"))
                return

            s.update(tr("获取版本元数据..."))
            raw_version_meta = await self.fetcher.fetch_model_into_pool(
                key=f'versionmeta-{version_id}.json',
                fetcher=lambda : self.session.typed(entry.url),
                filespec=FileSpec(checksum=entry.sha1, algorithm='sha1')
            )

            version_meta = unify(raw_version_meta, self.api.models.VersionMetaModel)

            s.update(tr("校验本地文件"))

            sdl = version_meta.downloads.server

            if sdl is None:
                console.error(tr("指定的版本不提供服务端"))
                return

            with self.file_cacher.open(f"server-{version_id}.jar") as file:
                result = await self.file_validator.validate(
                    file,
                    FileSpec(
                        size=sdl.size,
                        checksum=sdl.sha1,
                    )
                )


            # if result.ok:




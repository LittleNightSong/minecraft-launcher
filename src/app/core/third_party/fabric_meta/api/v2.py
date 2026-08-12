from app.core.network import Session
from ..models.v2 import SupportedVersionListItem, LoaderListItem, LoaderInfo


class FabricMetaV2:
    base_url = 'https://meta.fabricmc.net/v2'

    def __init__(self, session: Session):
        self.session = session

    def join_url(self, sub_url):
        return f'{self.base_url}{sub_url}'

    async def fetch_supported_versions(self):
        return await self.session.typed(
            self.join_url('/versions'),
            type=list[SupportedVersionListItem]
        )

    async def fetch_loaders(self, game_version: str | None = None):
        if game_version is None:
            return await self.session.typed(
                self.join_url('/versions/loader'),
                type=list[LoaderListItem]
            )
        else:
            return await self.session.typed(
                self.join_url('/versions/loader/{}'),
                game_version,
                type=list[LoaderListItem]
            )

    async def fetch_loader_info(self, game_version: str, loader_version: str):
        return await self.session.typed(
            self.join_url('/versions/loader/{}/{}'), game_version, loader_version,
            type=LoaderInfo
        )
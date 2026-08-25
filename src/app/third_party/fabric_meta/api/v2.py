from app.core.network import Session
from app.third_party.fabric_meta.models import v2 as _models
from app.third_party.fabric_meta.models.v2 import SupportedVersionListItem, LoaderInfo


class FabricMetaV2:
    models = _models

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

    async def fetch_loaders_by_game(self, game_version: str) -> list[_models.LoaderDetailListItem]:
        return await self.session.typed(
            self.join_url('/versions/loader/{}'),
            game_version,
            type=list[_models.LoaderDetailListItem]
        )

    async def fetch_loader_info(self, game_version: str, loader_version: str) -> LoaderInfo:
        return await self.session.typed(
            self.join_url('/versions/loader/{}/{}'), game_version, loader_version,
            type=LoaderInfo
        )

    async def fetch_loader_profile(self, game_version: str, loader_version: str) -> _models.LoaderProfile:
        return await self.session.typed(
            self.join_url('/versions/loader/{}/{}/profile/json'),
            game_version, loader_version,
            type=_models.LoaderProfile
        )
import urllib.parse

from app.core.network import Session
from . import models as _models


class NeoForgeMavenAPI:
    models = _models

    def __init__(self, session: Session):
        self.session = session

    async def fetch_metadata(self):
        url = 'https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml'
        return _models.MavenMetadata.from_string(await self.session.text(
            url, headers={

            }
        ))

    def get_installer_url(self, version: str):
        version = urllib.parse.quote_plus(version).removeprefix('/')
        url = "https://maven.neoforged.net/releases/net/neoforged/neoforge/{0}/neoforge-{0}-installer.jar"

        return url.format(version)

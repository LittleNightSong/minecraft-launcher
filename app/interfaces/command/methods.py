from app.i18n import tr
from app.interfaces.command.common import console, session


async def get_version_manifest():
    with console.status(tr("获取版本清单")):
        return await session.call("https://piston-meta.mojang.com/mc/game/version_manifest_v2.json")



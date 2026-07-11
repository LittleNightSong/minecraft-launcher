import asyncio

from rich import print

from app.core.minecraft import VersionMetaModel
from app.core.minecraft.api import MinecraftAPI
from app.core.network.session import session


def check_classifiers(meta: VersionMetaModel):
    # 查找libraries是否有 classifier 字段
    for lib in meta.libraries:
        if lib.downloads.classifiers:
            return True

    return False


def check_need_extract(meta: VersionMetaModel):
    for lib in meta.libraries:
        if lib.natives:
            return True

    return False


async def main():
    async with session:
        api = MinecraftAPI(session)
        manifest = await api.get_version_manifest()

        versions = manifest.versions
        l, r = 0, len(versions)

        while l < r:
            mid = (l + r) // 2
            print("检查", versions[mid].id)
            meta = await session.call(
                url=versions[mid].url,
                type=VersionMetaModel
            )

            # if check_classifiers(meta):
            if check_need_extract(meta):
                r = mid
                print(f"通过；重新设置区间 [{l}, {r}]")
            else:
                l = mid + 1
                print(f"未通过；重新设置区间 [{l}, {r}]")

        meta = await session.call(
            url=versions[r].url,
            type=VersionMetaModel
        )

        print("结果：", meta.id, "是第一个不需要解压本地库的版本")
        print(meta)


asyncio.run(main())

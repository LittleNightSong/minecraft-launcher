from typing import Literal

import typer
from niquests import HTTPError

from app.core.i18n import tr
from app.core.network import Session
from app.third_party.mojang import MinecraftAPI
from app.interfaces.commandline.base import CommandGroup, console
from app.interfaces.commandline.base.command_base import command


class MojangAPICommands(CommandGroup):
    """
    对 mojang 公开 API 的简单封装，目前仅支持查询玩家 ID 和名称的功能
    """
    name = 'mojang'
    commands = ['uuid', 'name']

    # noinspection attribute-outside-init
    async def init(self):
        self.session = Session()
        self.api = MinecraftAPI(self.session)


    async def cleanup(self, exc_type, exc_val, exc_tb):
        await self.session.close()

    async def uuid(
            self,
            username: str,
            mode: Literal['online', 'offline', 'rollback'] = 'rollback',
    ):
        """
        获取玩家的 [uuid]UUID[/]

        :param username: 被查询玩家的名称
        :param mode: 查询方式 `online` 在线查询，`offline` 以离线登录的形式计算，`rollback` 会在玩家不存在时自动切换为离线查询
        """
        with console.status(tr("查询中")):
            match mode:
                case 'rollback':
                    result = await self.api.get_player_uuid(username)
                case 'online':
                    try:
                        result = await self.api.query_player_uuid(username)
                    except HTTPError as e:
                        if e.response.status_code == 404:
                            console.error(tr("此用户不存在"))
                            raise typer.Exit()
                        else:
                            raise e
                case 'offline':
                    result = self.api.calc_player_uuid(username)

        console.print(tr("用户 {} 的 UUID 为 {}", username, result))

    @command(name='name')
    async def name_(self, uuid: str):
        """
        从 UUID 反推用户名称（仅在线模式）

        :param uuid: 用户的 UUID
        """
        try:
            with console.status(tr("查询中")):
                result = await self.api.query_player_name(uuid)
            console.print(tr("名称：{}\nUUID：{}", result, uuid))
        except HTTPError as e:
            if e.response.status_code == 404:
                console.error(tr("此用户不存在"))
            else:
                raise e



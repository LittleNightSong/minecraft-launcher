import asyncio

import typer
from loguru import logger
from rich.console import Group
from rich.panel import Panel

from app.core.configs import cfg
from app.core.i18n import tr
from app.interfaces.commandline.base import find_repository
from app.interfaces.commandline.base.command_base import CommandGroup
from app.interfaces.commandline.base.console_extensions import console
from app.interfaces.commandline.base.convert_text_component import convert as convert_text
from app.core.server import ping_server


def safe_truediv(a, b):
    if b == 0:
        return float('inf')
    else:
        return a / b


class ServerCommandGroup(CommandGroup):
    name = 'server'
    commands = ['ping', 'add', 'list', 'play']

    def show_server_info(self, response, delay, name=None, bind=None):
        r = response
        players = r.players
        status_text = tr(
            "当前在线 [repr.number]{}[/] 人，最大承载量 [repr.number]{}[/] 人 "
            "(占用率：[repr.number]{:.2f}[/]%，延迟：[repr.number]{}[/]ms)",
            players.online, players.max, safe_truediv(players.online, players.max) * 100, delay
        )

        console.print(
            Panel(
                title=f'[bold]{name}[/]' if name else None,
                renderable=Group(
                    convert_text(r.description) or tr("暂不支持文本组件格式") if r.description else tr("未指定名称"),
                    '\n',
                    f"[dim]{tr('版本要求/服务器版本：')}{r.version.name if r.version else tr('未知')}",
                    # '\n',
                    status_text,

                    *([tr("实例 [bold]{}[/bold] 被用于进入此服务器", bind)] if bind else []),

                    fit=False
                ),
                border_style='yellow'
            )
        )

    async def ping(
            self,
            addr: str, *,
            timeout=typer.Option(None, '-t', '--timeout')
    ):
        console.print(tr("正在获取服务器 {} 的状态", addr))
        try:
            response, delay = await ping_server(addr, timeout=timeout)
            self.show_server_info(response, delay)

        except TimeoutError:
            console.error(tr("连接服务器超时"))
            raise typer.Abort()

    async def add(
            self,
            name, *,
            addr: str = typer.Option(..., '-a', '--addr'),
            bind: str = typer.Option(..., '-b', '--bind'),
            show_server_info: bool = typer.Option(False, '-s', '--show'),
            yes: bool = typer.Option(False, '-y', '--yes'),
    ):
        """
        记录一个新的服务器

        :param name: 服务器名称
        :param addr: 服务器地址
        :param bind: 绑定的实例
        :param show_server_info: 是否 PING 展示服务器信息
        :param yes: 跳过确认信息
        """
        if show_server_info:
            await self.ping(addr, timeout=15)  # 如果 ping 失败，抛出 Abort 或者 Timeout 错误，不会再继续执行

        if cfg.exists_server(name):
            console.confirm(tr("服务器 [bold]{}[bold] 已存在，是否覆盖？", name), abort=True, skip=yes)

        cfg.add_server(name, addr, bind)

        console.print(tr("已添加新的服务器 [bold]{}[/bold]", name))

    async def list(
            self, *,
            skip_offline: bool = typer.Option(False, '-s', '--skip-offline'),
            ping: bool = typer.Option(True, '-P', '--ping'),
    ):
        """
        列举本地记录的服务器，可选 PING 服务器

        :param skip_offline: 跳过无法连接的服务区，如果不启用 PING，此选项将无效
        :param ping: 列举时 PING 服务器
        """

        servers = cfg.get_all_servers()

        ping_results = {}
        if ping:
            ping_tasks = [(rec, asyncio.create_task(ping_server(rec.addr, 10))) for rec in servers]

            for rec, task in ping_tasks:
                try:
                    ping_results[rec] = await task
                except (TimeoutError, AssertionError) as e:
                    logger.opt(exception=e).error("PING 服务器 {} 时发生错误", rec)

        for s in servers:
            res = ping_results.get(s.name)

            if res is None and ping and skip_offline:  # 只有开启 PING 的情况下此选项才生效
                continue

            # 开始构建输出
            if res is None:
                console.print(
                    Panel(
                        title=f'[bold]{s.name}[/]',
                        renderable=Group(
                            tr("启动使用的版本：{}", s.bind)
                        )
                    )
                )
            else:
                self.show_server_info(*res, name=s.name, bind=s.bind)

    async def play(
            self, name: str,
            ping: bool = typer.Option(True, '-P', '--ping'),
            yes: bool = typer.Option(False, '-y', '--yes'),
            repo: str | None = typer.Option(None, '-r', '--repository'),
    ):
        """
        启动游戏并进入选中的服务器

        :param name: 服务器名称
        :param ping: 启动器是否 PING 服务器
        :param yes: 跳过确认环节
        :param repo: 仓库名称/路径
        """
        # 首先检查选中的服务器存在性
        server = cfg.get_server(name)
        if server is None:
            console.error(tr("指定名称的服务器不存在"))
            raise typer.Abort()

        minecraft = find_repository(repo)
        # 检查绑定的实例

        if not minecraft.versions.exists(server.bind):
            console.error(tr("此服务器的绑定实例 [bold]{}[/bold] 不存在", server.bind))
            raise typer.Abort()

        if ping:
            try:
                response, delay = await ping_server(server.addr, timeout=15)
                self.show_server_info(response, delay, name=server.name, bind=server.bind)
            except TimeoutError:
                console.confirm(
                    tr("服务器无法连接或连接缓慢，是否继续？"),
                    skip=yes,
                    abort=True
                )
            except Exception as e:
                logger.opt(exception=e).error("无法获取服务器状态 {}", server)
                console.confirm(
                    tr("无法确定服务器状态，是否继续？"),
                    skip=yes,
                    abort=True
                )

        # 然后直接调用 launch 命令
        from app.interfaces.commandline.commands.instances_commands.launch import LaunchCommand
        await LaunchCommand.call(
            name=server.bind,  # 实例名称
            repo=minecraft.path,
            quick_play=f'server:{server.addr}',
        )

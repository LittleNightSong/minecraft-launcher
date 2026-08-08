from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, ListView, ListItem, Label, Collapsible

from app.core.i18n import tr
from app.core.minecraft import VersionManifestModel, MinecraftVersion


class VersionListItem(ListItem):
    """可多选的版本列表项"""

    def __init__(self, version_item: MinecraftVersion, selected: bool = False, selectable=True) -> None:
        self.version_item: MinecraftVersion = version_item
        self.selected = selected
        self.selectable = selectable

        super().__init__(Label(self._render_label()))

    def _render_label(self) -> str:
        check = r"\[x]" if self.selected else "[ ]"

        if self.version_item.type == 'release':
            part_type = f'[green]R[/]'
        else:
            part_type = f'[light_purple]S[/]'

        if self.selected:
            version_part = f'[bold]{self.version_item.version}[/bold]'
        else:
            version_part = self.version_item.version

        if self.selectable:
            return f'{check} {part_type} {version_part}'
        else:
            return f'{part_type} {version_part}'

    def toggle(self) -> None:
        self.selected = not self.selected
        self.children[0].update(self._render_label())  # 更新 Label 内容

        if self.selected:
            self.app.query_one(VersionsView).add_version(self.version_item)
        else:
            self.app.query_one(VersionsView).remove_version(self.version_item)

    def on_click(self, event: events.Click):
        self.toggle()
        event.stop()


class ButtonLikeLabel(Label, can_focus=True):
    def __init__(self, text, callback=None):
        super().__init__(text)
        self.callback = callback

    def on_focus(self, event: events.Focus):
        self.parent.focus()

    def on_click(self, event: events.Click):
        if self.callback is not None:
            self.callback(event)


class VersionsSelector(VerticalScroll):
    def __init__(
            self,
            versions: list[MinecraftVersion],
            title,
            id: str | None = None,
            foldable: bool = True, fold: bool = True
    ):
        self.versions = versions
        self.foldable = foldable
        self.fold = fold
        self.title = title
        self.collasible = Collapsible(title=self.title, collapsed=self.fold)
        self.list_view = ListView(*[VersionListItem(i) for i in versions])

        super().__init__(id=id)

    def compose(self) -> ComposeResult:
        if self.foldable:
            with self.collasible:
                yield self.list_view
        else:
            yield self.list_view

    def toggle_hidden(self, event):
        c = self.collasible
        c.collapsed = not c.collapsed

    @property
    def user_selects(self):
        return [
            i.version_item
            for i in self.list_view.children
            if isinstance(i, VersionListItem) and i.selected
        ]

    def on_key(self, event: events.Key) -> None:
        if event.key == 'space':
            if self.list_view.index is not None:
                item = self.list_view.children[self.list_view.index]
                if isinstance(item, VersionListItem):
                    item.toggle()
                    event.stop()

    def on_focus(self, event: events.Focus) -> None:
        if self.foldable:
            self.list_view.display = True

    def on_blur(self, event: events.Blur) -> None:
        if self.foldable:
            self.list_view.display = False


class VersionsView(ListView):
    def __init__(self, versions: list[MinecraftVersion] | None = None, id: str | None = None):
        self.versions = versions or []
        self.mapping = {}

        widgets = [VersionListItem(version) for version in self.versions]

        for w in widgets:
            self.mapping[w.version_item] = w

        super().__init__(*widgets, id=id)

    def add_version(self, version: MinecraftVersion) -> None:
        widget = self.mapping.get(version)

        if widget:
            self.remove_children([widget])
        else:
            self.mapping[version] = widget = VersionListItem(version, selectable=False)

        self.mount(widget)

    def remove_version(self, version: MinecraftVersion) -> None:
        widget = self.mapping.pop(version, None)
        if widget:
            self.remove_children([widget])


class VersionSelectorApp(App):  # TODO
    """Textual 应用：选择要安装的版本"""
    CSS = """
    #selected-versions {
        width: 25
    }
    ListView {
        height: auto;
        overflow-y: hidden;
    }
    Collapsible {
        height: auto;
        overflow-y: hidden;
    }
    """

    def __init__(self, manifest: VersionManifestModel):  # (id, type)
        super().__init__()
        self.manifest = manifest  # 版本清单
        self.selected_versions = []  # 最终选中的版本 ID

    def compose(self) -> ComposeResult:
        yield Header()

        groups = self.manifest.separate()
        title_mapping = {
            'release': tr("正式版"),
            'snapshot': tr("快照版"),
            'rc': tr("候选发布版"),
            'pre': tr("预发布版"),
            'april fool': tr("愚人节版本"),
            'old': tr("远古版本"),
        }

        def selector_for(group: str, auto_hide: bool = True, id: str | None = None):
            versions = groups[group]
            title = title_mapping[group]

            return VersionsSelector(versions, title, id=id, foldable=auto_hide)

        yield Horizontal(
            VersionsView(id='selected-versions'),
            Vertical(
                VersionsSelector(
                    [
                        MinecraftVersion(i.id)
                        for i in self.manifest.latest_items
                    ],
                    title=tr("最新版本"),
                    foldable=False
                ),
                selector_for('release'),
                selector_for('april fool'),
                selector_for('snapshot'),
                selector_for('old'),
                selector_for('rc'),
                selector_for('pre'),
            )
        )
        yield Footer()
        yield Label("按 空格 切换选中，按 Enter 确认安装，按 Esc 取消", id="status")

    def on_key(self, event: events.Key) -> None:
        """处理键盘事件"""

        if event.key == "enter":
            # 确认选择，收集所有选中的版本 ID
            self.selected_versions = [
                j
                for i in self.query(VersionsSelector)
                for j in i.user_selects
            ]
            if not self.selected_versions:
                # 如果未选择任何版本，给出提示并留在界面
                self.query_one("#status").update("未选择任何版本，请至少选择一个")
                return

            self.exit(result=self.selected_versions)  # 退出并返回结果

        elif event.key == "escape":
            # 取消，返回空列表
            self.selected_versions = []
            self.exit(result=[])

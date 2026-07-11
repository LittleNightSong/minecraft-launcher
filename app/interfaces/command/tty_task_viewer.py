from typing import Any

from rich.live import Live
from rich.panel import Panel
from rich.table import Table, Column
from rich.text import Text

from app.core.common import filesize
from app.core.common.task import TaskProgress, ProgressKind


# Status/Progress Description Extra-Info
def format_task_message(task: TaskProgress):  # Finished
    if not task.running:
        return Text("⋯", style="blue"), task.description, task.extra_info

    if task.error:
        return f'❌ {task.error}', task.description, task.extra_info

    match task.progress_kind:
        case ProgressKind.percent:
            progress = round(task.progress / task.total, 1)
        case ProgressKind.nom:
            progress = f'{task.progress}/{task.total or "Unknown"}'
        case ProgressKind.size:
            progress = f'{filesize.format_filesize(task.progress)}/{filesize.format_filesize(task.total)}'

        case _:
            raise TypeError(f'Unknown progress kind: {task.progress_kind}')

    return progress, task.description, task.extra_info


class TTYTaskViewer:
    def __init__(self, console=None, fps: int | None = None):
        self.live = None
        self.title = None
        self.traced_tasks: list[TaskProgress] = []
        self.fps = fps

        self._console = console

    def update(self):
        rows = [format_task_message(task) for task in self.traced_tasks if task.visible]

        table = Table(
            Column("Status/Progress", min_width=5),
            "Description",
            "Extra Info",
            show_header=False, box=None
        )

        for row in rows:
            table.add_row(*row)

        # print('Update Progress:', rows)
        return Panel(
            table,
            title=self.title,
            title_align='left',
            border_style='yellow bold',
            highlight=True
        )

    def trace(self, task: TaskProgress):
        self.traced_tasks.append(task)

    def new_task(
            self, *,
            total: int | float | None = None,
            progress: int | float = 0,
            description: str | Any | None = None,
            extra_info: str | None = None,
            progress_kind: ProgressKind = ProgressKind.percent,
            visible: bool = True,
            running: bool = False,
            error: Any | None = None
    ):
        task = TaskProgress(
            total=total,
            progress=progress,
            description=description,
            extra_info=extra_info,
            progress_kind=progress_kind,
            visible=visible,
            running=running,
            error=error
        )

        self.trace(task)
        return task

    def untrace(self, task: TaskProgress):
        self.traced_tasks.remove(task)

    def clear(self):
        self.traced_tasks = []

    def start(self):
        self.live = Live(
            get_renderable=self.update,
            console=self._console,
            auto_refresh=True,
            refresh_per_second=self.fps or 1
        )
        self.live.start()

    def stop(self):
        self.live.refresh()
        self.live.stop()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

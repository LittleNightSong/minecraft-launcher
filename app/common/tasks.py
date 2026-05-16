import rich
from rich import markup
from rich.console import RenderableType
from rich.progress import TaskID, Progress, ProgressColumn, TextColumn, BarColumn


class ProgressTask:
    def __init__(self, progress: Progress, task_id: TaskID):
        self.progress = progress
        self.task_id = task_id

    def advance(self, value):
        self.progress.advance(self.task_id, value)

    def update(self, **kwargs):
        self.progress.update(**kwargs)


class BaseTask:
    progress_task: ProgressTask = None

    def __init__(self):
        self._total = None
        self._progress = 0
        self._description = None
        self._status = None
        self._visible = True

    @property
    def total(self):
        return self._total

    @total.setter
    def total(self, value):
        self._total = value
        self.progress_task.update(total=value) if self.progress_task else None

    @property
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, value):
        self._progress = value
        self.progress_task.update(progress=value) if self.progress_task else None

    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, value):
        self._description = value
        self.progress_task.update(description=value) if self.progress_task else None

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, value):
        self._visible = value
        self.progress_task.update(visible=value) if self.progress_task else None

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        self._status = value
        self.progress_task.update(status=value) if self.progress_task else None

    async def run(self):
        ...


class StatusColumn(ProgressColumn):
    def render(self, task) -> RenderableType:
        return markup.render(task.fields.get('status', ''))


class TaskManager:
    def __init__(self):
        self.progress = rich.progress.Progress(
            StatusColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            refresh_per_second=2, transient=True
        )
        self.tasks = []

    def add_task(self, task: BaseTask):
        self.tasks.append(task)
        task.progress_task = ProgressTask(self.progress, self.progress.add_task(
            task.description, total=task.total, completed=task.progress
        ))

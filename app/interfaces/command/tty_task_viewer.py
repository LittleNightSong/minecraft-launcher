from rich import markup

from app.common import filesize
from app.common.tasks import BaseTask, SequenceTask, ParallelTask, ProgressKind


class TTYTaskViewer:
    def __init__(self):
        #                             Task     Depth
        self.traced_tasks: list[tuple[BaseTask, int]] = []

    def trace_r(self, task: BaseTask, depth: int = 0):  # Finished
        if isinstance(task, (SequenceTask, ParallelTask)):
            self.traced_tasks.append((task, depth))
            for sub_task in task.tasks:
                self.traced_tasks.append((sub_task, depth + 1))
                self.trace_r(sub_task, depth + 1)
        else:
            self.traced_tasks.append((task, depth))

    # Status/Progress Description Extra-Info
    def _process_task(self, task: BaseTask, depth: int):  # Finished
        if coro := task.coro:
            if coro.done():
                if exc := coro.exception():
                    return '\t' * depth + f'❌ {exc}', task.description, task.extra_info
                elif coro.cancelled():
                    return '\t' * depth + '❌ Cancelled'
            #     else:
            #         status = 'OK', None
            # else:
            #     status = 'Running', None
        else:
            return markup.render('\t' * depth + "[blue]⋯[/blue]"), task.description, task.extra_info

        match task.progress_kind:
            case ProgressKind.percent:
                progress = round(task.progress / task.total, 1)
            case ProgressKind.nom:
                progress = f'{task.progress}/{task.total}'
            case ProgressKind.size:
                progress = f'{filesize.format_filesize(task.progress)} / {filesize.format_filesize(task.total)}'

            case _:
                raise TypeError(f'Unknown progress kind: {task.progress_kind}')

        return progress, task.description, task.extra_info

    def update(self):
        rows = []
        for task, depth in self.traced_tasks:
            if task.visible:
                rows.append(self._process_task(task, depth))

        # TODO: Show in tables

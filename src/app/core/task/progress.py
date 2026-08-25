from app.core.task.task import TaskProgress


class Progress:
    def __init__(self):
        self.tasks = []

    def add_task(self, task: TaskProgress):
        self.tasks.append(task)
        self.on_add_task(task)

    def remove_task(self, task: TaskProgress):
        self.tasks.remove(task)
        self.on_remove_task(task)

    def push_task(self, task: TaskProgress):
        self.tasks.append(task)
        self.on_add_task(task)

    def pop_task(self):
        task = self.tasks.pop(-1)
        self.on_remove_task(task)

    def start(self):
        ...

    def stop(self):
        ...

    def on_add_task(self, task: TaskProgress):
        ...

    def on_remove_task(self, task: TaskProgress):
        ...
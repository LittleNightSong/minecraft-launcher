import asyncio

from app.core.common import Worker
from app.core.common.file_validator import FileValidator


class CommonFileChecker(Worker):
    def __init__(self, validator: FileValidator | None = None):
        self.result_groups = [[], ]
        self.validator = validator if validator else FileValidator()
        self.vis = set()

        super().__init__()

    async def process_one(self, input):
        if isinstance(input, list):
            tasks = []
            for item in input:
                if item.key is not None and item.key in self.vis:
                    continue
                if item.key is not None:
                    self.vis.add(item.key)

                tasks.append(asyncio.create_task(self.validator.validate(item)))

            self.result_groups.append(tasks)
        else:
            task = asyncio.create_task(self.validator.validate(input))
            self.result_groups[0].append(task)

    async def process_result(self):
        return [
            await j
            for i in self.result_groups
            for j in i
        ]
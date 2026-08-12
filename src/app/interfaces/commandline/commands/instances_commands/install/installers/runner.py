import asyncio
from contextlib import contextmanager

from app.core.network.downloader import Downloader
from .base_installer import Installer, LocalFileValidateRequest, PoolFileValidateRequest, ValidateResponse, \
    ValidateResponseClassifiers, Reasons, InstallContext


class InstallerRunner:
    def __init__(
            self,
            installer: Installer,
            context: InstallContext
    ):
        self.installer = installer
        self.context = context

        self.file_validator = context.file_validator
        self.install_spec = context.spec
        self.repository = context.repository

        data = self.repository.launcher_data

        self.file_cacher = data.file_cacher
        self.model_cacher = data.model_cacher

        self.task_ids_mro = None
        self.task_groups_mro = None
        self.validate_tasks = None
        self.unnamed_tasks = None

        self.download_plans = None

        self.status = (None, True)

    @contextmanager
    def chstat(self, __from, __to, /):
        assert (
                self.status[0] == __from and self.status[1] is True
        ), (
            "不合法的状态转换 {!r}: {!r} (期望 {!r}: True ) -> {}".format(*self.status, __from, __to)
        )
        self.status = __to, False
        try:
            yield
        finally:
            self.status = __to, True

    async def fetch(self):
        with self.chstat(None, 'fetch'):
            await self.installer.fetch()

    async def _collect(self):
        ls = [i async for i in self.installer.collect()]

        groups = {}
        id_mro = {}

        async def validate_pool_file(filename, spec):
            with self.file_cacher.open(filename) as file:
                return await self.file_validator.validate(file, spec)

        def _get_task(request):
            match request:
                case LocalFileValidateRequest(filename=filename, spec=spec):
                    return self.file_validator.validate(filename, spec)
                case PoolFileValidateRequest(filename=filename, spec=spec):
                    return validate_pool_file(filename, spec)
                case r:
                    raise NotImplementedError(r)

        def get_task(request):
            return asyncio.create_task(_get_task(request))

        tasks = []
        unnamed_tasks = []

        for request in ls:
            task = get_task(request)
            tasks.append(task)

            req_id = request.id
            req_group = request.group

            if req_id:
                if req_id in id_mro:
                    await self.interrupt(Reasons.BAD_VALIDATE_REQUEST)
                id_mro[req_id] = request, task
            if req_group:
                groups.setdefault(req_group, []).append((request, task))

            if not req_id and not req_group:  # 不能出现数据丢失，就算没有标识符也得记录下来
                unnamed_tasks.append((request, task))

        (
            self.validate_tasks,
            self.task_ids_mro,
            self.task_groups_mro,
            self.unnamed_tasks
        ) = (
            tasks,
            id_mro,
            groups,
            unnamed_tasks
        )

    async def collect(self):
        with self.chstat('fetch', 'collect'):
            await self._collect()

    def validate(self):
        return asyncio.as_completed(self.validate_tasks), len(self.validate_tasks)

    async def _analyze(self):
        response_groups = {
            k: [
                ValidateResponse(
                    request=req,
                    result=await res_task
                )
                for req, res_task in results
            ]
            for k, results in self.task_groups_mro.items()
        }

        response_ids = {
            k: (
                ValidateResponse(
                    request=req,
                    result=await res_task
                )
            )

            for k, (req, res_task) in self.task_ids_mro.items()
        }

        unnamed_tasks = [
            ValidateResponse(request=req, result=await res_task)
            for req, res_task in self.unnamed_tasks
        ]

        classifiers = ValidateResponseClassifiers(
            groups=response_groups,
            ids=response_ids,
            unnamed=unnamed_tasks
        )

        plans = [i async for i in self.installer.analyze(classifiers)]
        self.download_plans = plans

    async def analyze(self):
        with self.chstat('collect', 'analyze'):
            await self._analyze()

    def start_download(self, downloader: Downloader):
        with self.chstat('analyze', 'start_download'):
            return [
                downloader.create_task(
                    plan
                )
                for plan in self.download_plans
            ]

    async def interrupt(self, reason: Reasons, stage: str | None = None):
        await self.installer.on_interrupt(
            stage or self.status[0],  # type: ignore
            reason
        )

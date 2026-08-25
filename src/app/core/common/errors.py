from contextlib import contextmanager

from loguru import logger
from msgspec.inspect import UnionType

from app.core.i18n.translator import tr


class ExceptionForUser(Exception):
    def __init__(self, exc):
        self.exc = exc

    def __str__(self):
        return f'({self.exc.__class__.__name__}) {self.exc}'


class FormattedExceptionBase(Exception):
    type: str

    def __init__(self, __message, *args, **kwargs):
        self._message = __message
        self._args = args
        self._kwargs = kwargs

    def get_final_message(self):
        return tr(self.type) + ': ' + tr(self._message, *self._args, **self._kwargs)

    def __str__(self):
        return self.get_final_message()


class MaximumRetry(FormattedExceptionBase):
    type = '重试超限'


class ConflictInstall(FormattedExceptionBase):
    type = '安装冲突'


class InvaildInstance(FormattedExceptionBase):
    type = '无效的实例'


class RepositoryNotFound(FormattedExceptionBase):
    type = '仓库未找到'


class VersionNotFound(FormattedExceptionBase):
    type = '版本未找到'

class VersionNotSupported(FormattedExceptionBase):
    type = '版本不支持'


class NetworkError(FormattedExceptionBase):
    type = '网络错误'


@contextmanager
def accept_errors(errors: type[BaseException] | tuple[type[BaseException], ...] | UnionType | None = None):
    try:
        yield
    except errors as e:
        logger.opt(exception=e).warning("已忽略异常 {}", e.__class__.__name__)
        pass

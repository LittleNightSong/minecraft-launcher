from abc import abstractmethod
from typing import Self

from .base_installer import Installer, InstallContext


class GeneralInstaller(Installer):
    def __init__(self, context: InstallContext):
        self.context = context

        self._install_version_meta = None
        self._install_group = None

    @classmethod
    @abstractmethod
    async def get_installer(cls, context: InstallContext) -> Self | None:
        ...

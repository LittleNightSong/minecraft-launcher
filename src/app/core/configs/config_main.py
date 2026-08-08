import typing
from pathlib import Path
from typing import Generator

import msgspec

from app.core.common import read_model, write_model
from .records import RepositoryRecord, UserIDRecord, JavaRecord, ServerRecord


class RepositoriesModel(msgspec.Struct):
    latest: str | None = None
    repository_list: list[RepositoryRecord] = msgspec.field(default_factory=list)

    def search(self, name: str) -> tuple[RepositoryRecord, int] | None:
        for i, record in enumerate(self.repository_list):
            if record.name == name:
                return record, i
        return None

    def get(self, name: str) -> RepositoryRecord:
        result = self.search(name)
        if result is not None:
            return result[0]
        else:
            raise ValueError(f"Repository {name} not found")

    def add(self, name: str, path: str):
        result = self.search(name)
        if result is not None:
            self.repository_list.pop(result[1])

        self.repository_list.append(RepositoryRecord(name, path))

    def remove(self, name: str):
        result = self.search(name)
        if result is not None:
            self.repository_list.pop(result[1])
            if self.latest == name:
                self.latest = self.repository_list[-1].name  # 重设 latest 字段
        else:
            raise ValueError(f"Repository {name} not found")

    def set_current(self, name: str, path: str | None = None):
        if self.search(name) is None:
            if path:
                self.add(name, path)
            else:
                raise ValueError(f"Repository {name} not found")

        self.latest = name

    def get_current(self) -> RepositoryRecord | None:
        if self.latest is None:
            if self.repository_list:
                record = self.repository_list[-1]
                self.latest = record.name
                return record
            else:
                return None
        else:
            return self.search(self.latest)[0]  # type: ignore  # 我们保证这里不会报错


class ConfigStruct:
    repositorys: RepositoriesModel
    user_ids: list[UserIDRecord]
    javas: set[JavaRecord]
    servers: dict[str, ServerRecord]


class Config:
    def __init__(self):
        self.path = None
        self._cfg = ConfigStruct()

    def set_path(self, path):
        self.path = Path(path)
        return self

    def load(self, path=None):
        self.path = path = path or self.path

        cfg = self._cfg
        cfg.user_ids = read_model(
            file=path / 'ids.json',
            type=list[UserIDRecord],
            default_factory=list
        )
        cfg.repositorys = read_model(
            file=path / 'repos.json',
            type=RepositoriesModel,
            default_factory=RepositoriesModel
        )
        cfg.javas = read_model(
            file=path / 'javas.json',
            type=set[JavaRecord],
            default_factory=set
        )

        cfg.servers = read_model(
            file=path / 'servers.json',
            type=dict[str, ServerRecord],
            default_factory=dict
        )

        return self

    def save(self):
        path = self.path

        write_model(
            file=path / 'ids.json',
            obj=self._cfg.user_ids
        )
        write_model(
            file=path / 'repos.json',
            obj=self._cfg.repositorys
        )
        write_model(
            file=path / 'javas.json',
            obj=self._cfg.javas
        )

        write_model(
            file=path / 'servers.json',
            obj=self._cfg.servers
        )

    def get_selected_repository(self) -> RepositoryRecord | None:
        return self._cfg.repositorys.get_current()

    def set_selected_repository(self, name, path: Path | None = None):
        self._cfg.repositorys.set_current(name, str(path))

    def add_repository(self, name: str, path: Path):
        self._cfg.repositorys.add(name, str(path))

    def remove_repository(self, name: str):
        self._cfg.repositorys.remove(name)

    def exists_repository(self, name: str):
        return bool(self._cfg.repositorys.search(name))

    def get_repository(self, name: str):
        return self._cfg.repositorys.get(name)

    def list_repositories(self):
        return list(self._cfg.repositorys.repository_list)

    def add_java(self, path, type, major):
        self._cfg.javas.add(JavaRecord(path, type, major))

    def add_java_record(self, rec: JavaRecord):
        self._cfg.javas.add(rec)

    def clear_java_records(self):
        self._cfg.javas.clear()

    def has_java(self, major: int):
        for i in self._cfg.javas:
            if i.major == major:
                return True

        return False

    def has_java_forward(self, major):
        for i in self._cfg.javas:
            if i.major >= major:
                return True

        return False

    def get_all_javas(self) -> list[JavaRecord]:
        return list(self._cfg.javas)

    def get_java(self, major: int) -> JavaRecord | None:
        for i in self._cfg.javas:
            if i.major == major:
                return i
        return None

    def get_java_forward(self, major: int) -> JavaRecord | None:
        for i in self._cfg.javas:
            if i.major >= major:
                return i

        return None

    def get_javas(self, major: int) -> Generator[JavaRecord]:
        for i in self._cfg.javas:
            if i.major == major:
                yield i

    def get_javas_forward(self, major: int) -> Generator[JavaRecord] | None:
        for i in self._cfg.javas:
            if i.major >= major:
                yield i

    def add_server(self, name, addr, bind):
        self._cfg.servers[name] = ServerRecord(name, addr, bind)

    def get_server(self, name: str) -> ServerRecord | None:
        return self._cfg.servers.get(name)

    def get_all_servers(self):
        return list(self._cfg.servers.values())

    def exists_server(self, name: str) -> bool:
        return name in self._cfg.servers

    def remove_server(self, name: str):
        del self._cfg.servers[name]

    @typing.overload
    def modify_server(self, name, *, addr: str, bind: str):
        ...

    @typing.overload
    def modify_server(self, name, *, bind: str):
        ...

    @typing.overload
    def modify_server(self, name, *, addr: str):
        ...

    def modify_server(self, name, **changes):
        self._cfg.servers[name] = msgspec.structs.replace(self._cfg.servers[name], **changes)

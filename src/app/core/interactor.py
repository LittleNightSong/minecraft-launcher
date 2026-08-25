import typing


class Interactor(typing.Protocol):
    actor_id: str

    def status(self, text=None):
        ...

    def print(self, text):
        ...

    def log(self, text): ...
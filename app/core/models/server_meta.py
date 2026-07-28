from uuid import UUID

import msgspec

from app.core.models.text_component import TextComponent


class SinglePlayerStruct(msgspec.Struct):
    name: str
    id: UUID


class PlayersStruct(msgspec.Struct):
    max: int
    online: int
    sample: list[SinglePlayerStruct]


class VersionStruct(msgspec.Struct):
    name: str
    protocol: int


def fix_text_component(component: dict):
    component.setdefault('type', 'text')
    for item in component.get('extra', ()):
        if isinstance(item, dict):
            fix_text_component(item)


class ServerMeta(msgspec.Struct):
    players: PlayersStruct
    version: VersionStruct
    _description: str | dict | None = msgspec.field(name='description', default=None)  # TODO: Text Component Not Available

    @property
    def description(self) -> str  | TextComponent | None:
        if self._description is None or isinstance(self._description, str):
            return self._description
        else:
            fix_text_component(self._description)
            return msgspec.convert(self._description, TextComponent)



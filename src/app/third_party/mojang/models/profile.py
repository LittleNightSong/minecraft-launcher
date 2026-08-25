from uuid import UUID

import msgspec


class TexturesPropertyStruct(msgspec.Struct, tag_field='name', tag='textures'):
    class TexturesPropertyValueStruct(msgspec.Struct):
        class TexturesFieldStruct:
            class SkinStruct(msgspec.Struct):
                class MetadatStruct:
                    model: str

                url: str
                metadata: MetadatStruct | None = None

            class CapeStruct(msgspec.Struct):
                url: str

            SKIN: SkinStruct
            CAPE: CapeStruct | None = None

        timestamp: int
        profile_id: UUID = msgspec.field(name='profileId')
        profile_name: str = msgspec.field(name='profileName')
        textures: TexturesFieldStruct

    value: bytes

    def decode_value(self):
        return msgspec.json.decode(
            self.value,
            type=self.TexturesPropertyValueStruct
        )


type PropertyStructs = TexturesPropertyStruct


class PlayerProfile(msgspec.Struct, kw_only=True):
    id: UUID
    name: str
    legacy: bool = False
    properties: list[PropertyStructs]


import copy

import msgspec

from app.core.minecraft.color_code import FormatStyles, ColorStyles

# type TextComponent = TypeText | TypeTranslated | TypeScore | TypeSelector | TypeKeyBind
type TextComponent = TypeText


class BaseTextComponent(msgspec.Struct, kw_only=True):
    color: str | None = None
    font: str | None = None
    bold: bool | None = None
    italic: bool | None = None
    underlined: bool | None = None
    strikethrough: bool | None = None
    obfuscated: bool | None = None
    shadow_color: int | tuple[float, float, float, float] | str | None = None
    extra: list[TextComponent] | None = None

    # insertion: str | None = None
    # click_event: dict | None = None
    # keybind_event: dict | None = None

    def merge_styles(self, other: BaseTextComponent):
        self.color = other.color or self.color
        self.bold = other.bold or self.bold
        self.obfuscated = other.obfuscated or self.obfuscated
        self.italic = other.italic or self.italic
        self.font = other.font or self.font
        self.strikethrough = other.strikethrough or self.strikethrough
        self.shadow_color = other.shadow_color or self.shadow_color
        self.underlined = other.underlined or self.underlined

    @property
    def styles(self):
        styles = []
        if self.bold:
            styles.append(FormatStyles.bold)
        if self.strikethrough:
            styles.append(FormatStyles.strikethrough)
        if self.italic:
            styles.append(FormatStyles.italic)
        if self.obfuscated:
            styles.append(FormatStyles.obfuscated)
        # if self.shadow_color:
        if self.color:
            if self.color[0] == '#':
                assert len(self.color) == 7
                styles.append((  # RGB
                    int(self.color[1:2], base=16),
                    int(self.color[3:4], base=16),
                    int(self.color[5:6], base=16),
                ))
            else:
                styles.append(getattr(ColorStyles, self.color))
        if self.underlined:
            styles.append(FormatStyles.underline)

        return styles

    def copy(self):
        return copy.deepcopy(self)


class TypeText(BaseTextComponent, tag='text'):
    text: str

# class TypeTranslated(BaseTextComponent, tag='translatable', kw_only=True):
#     translate: str
#     fallback: str | None = None
#     with_data: list[TextComponent]


# class ScoreStruct(msgspec.Struct, kw_only=True):
#     name: str
#     objective: str


# class TypeScore(BaseTextComponent, tag='score', kw_only=True):
#     score: ScoreStruct
#
#
# class TypeSelector(BaseTextComponent, tag='selector', kw_only=True):
#     selector: str
#     separator: TextComponent = msgspec.field(
#         default_factory=lambda: msgspec.convert({'color': "gray", 'text': ", "}, TypeText))


# class TypeKeyBind(BaseTextComponent, tag='keybind', kw_only=True):
#     keybind: str

# NOTODO: Type NBT, Atlas, Player 作为启动器，我们无法解析动态组件，只需要实现静态组件的解析即可

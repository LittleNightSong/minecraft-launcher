import enum
from typing import NamedTuple

flag_char = '§'


class ColorStyles(tuple, enum.Enum):
    reset = 'r', None
    black = '0', (0, 0, 0)
    dark_blue = '1', (0, 0, 170)
    dark_green = '2', (0, 170, 0)
    dark_aqua = '3', (0, 170, 170)
    dark_red = '4', (170, 0, 0)
    dark_purple = '5', (170, 0, 170)
    gold = '6', (255, 170, 0)
    gray = '7', (170, 170, 170)
    dark_gray = '8', (85, 85, 85)
    blue = '9', (85, 85, 255)
    green = 'a', (85, 255, 85)
    aqua = 'b', (85, 255, 255)
    red = 'c', (255, 85, 85)
    light_purple = 'd', (255, 85, 255)
    yellow = 'e', (255, 255, 85)
    white = 'f', (255, 255, 255)

    # Bedrock Edition Only
    minecoin_gold = 'g', (214, 214, 5)
    material_quartz = 'h', (227, 212, 209)
    material_iron = 'i', (206, 202, 202)
    material_netherite = 'j', (68, 58, 59)
    material_redstone = 'm', (151, 22, 7)
    material_copper = 'n', (180, 104, 77)
    material_gold = 'p', (222, 177, 45)
    material_emerald = 'q', (17, 160, 54)
    material_diamond = 's', (44, 186, 168)
    material_lapis = 't', (33, 73, 123)
    material_amethyst = 'u', (235, 114, 20)
    material_resin = 'v', (235, 114, 20)
    party_blue_colr = 'w', (140, 179, 255)


    @property
    def bedrock_only(self):
        return self.name.startswith(('m', 'p'))

    @property
    def color(self):
        return self[1]

    @property
    def code(self):
        return self[0]

    def is_reset(self):
        return self[0] == 'r'

    @classmethod
    def from_code(cls, code: str):
        return cls._mapping[code]

    @classmethod
    def from_code_safe(cls, code: str):
        return cls._mapping.get(code)

    @classmethod
    def from_color(cls, color: tuple[int, int, int]):
        return cls._mapping[color]

    @classmethod
    def from_color_safe(cls, color: tuple[int, int, int]):
        return cls._mapping.get(color)


class FormatStyles(str, enum.Enum):
    reset = 'r'
    bold = 'l'
    italic = 'o'
    strikethrough = 'm'
    underline = 'n'
    obfuscated = 'k'

    def is_reset(self):
        return self == 'r'

    @property
    def java_only(self):
        if self in {self.strikethrough, self.underline}:  # 这两个在基岩版中已经变成了颜色代码，不再是格式代码
            return False
        else:
            return True

    @classmethod
    def from_code_safe(cls, code):
        return cls(code) if code in cls else None


def _make_mapping():
    mapping = {i.code: i for i in ColorStyles}
    mapping.update({
        i.color: i
        for i in ColorStyles
    })

    type.__setattr__(ColorStyles, '_mapping', mapping)


_make_mapping()


class Span(NamedTuple):
    styles: list[ColorStyles | FormatStyles]
    text: str


def blocks_from_text(text: str, strict=False, bedrock=False):
    components = []
    start = 0
    pos = 0
    while True:
        cur_pos = text.find(flag_char, start)

        if cur_pos == -1:
            remaing = text[pos + 2:]
            if remaing:
                components.append(remaing)
            break
        else:
            pos = cur_pos

        middle = text[start+1:pos] if start != 0 else text[:pos]
        components.append(middle) if middle else ...

        start = pos + 1

        # 这里为了防止 Index Out of the range
        assert start < len(text)

        # 查表
        char = text[start]  # pos + 1 = start

        if char in 'mn':
            if bedrock:
                style = ColorStyles.from_code(char)
            else:
                style = FormatStyles(char)
        else:
            style = ColorStyles.from_code_safe(char) or FormatStyles.from_code_safe(char)

            if isinstance(style, ColorStyles) and not bedrock and style.bedrock_only:
                style = None  # 无法代替，置为 None

        if style is None and strict:
            raise ValueError(f'Unsupported code {char!r}')

        components.append((style, char))

    return components


def spans_from_blocks(blocks: list[tuple | str]) -> list[Span]:
    spans = []
    style_stack = []
    style_set = set()

    for b in blocks:
        if isinstance(b, str):
            spans.append(Span(
                list(style_stack),
                b
            ))
        else:
            s, c = b

            if s is not None:
                if s.is_reset():
                    style_stack.clear()
                    style_set.clear()
                    continue

                if s not in style_set:
                    style_stack.append(s)
                    style_set.add(s)

    return spans


if __name__ == '__main__':
    text = "xxx§nXXX§rYYY§g"
    blocks = blocks_from_text(text)
    print(blocks)

    components = spans_from_blocks(blocks)
    print(components)

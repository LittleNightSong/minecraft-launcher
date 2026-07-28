from rich.color import Color
from rich.style import Style
from rich.text import Text

from app.core.minecraft.color_code import blocks_from_text, spans_from_blocks, ColorStyles, FormatStyles
from app.core.models.text_component import TextComponent, TypeText, BaseTextComponent


def get_raw_styles(styles: list[ColorStyles | FormatStyles], raw_styles: dict | None = None):
    raw_styles = raw_styles or {}
    for ts in styles:
        if ts in ColorStyles:
            raw_styles['color'] = Color.from_rgb(*ts.color)
        elif isinstance(ts, tuple):  # RGB 元组
            raw_styles['color'] = Color.from_rgb(*ts)
        elif ts in FormatStyles:
            match ts:
                case FormatStyles.bold:
                    raw_styles['bold'] = True
                case FormatStyles.italic:
                    raw_styles['italic'] = True
                case FormatStyles.underline:
                    raw_styles['underline'] = True
                case FormatStyles.strikethrough:
                    raw_styles['strike'] = True
                # case FormatStyles.obfuscated:
                #     pass  # 忽略不支持的格式

    return raw_styles


def _flatten(component: TextComponent, parent_styles: dict = None):
    parent_styles = parent_styles or {}
    if isinstance(component, TypeText):
        cur_styles = parent_styles.copy()
        cur_styles.update(get_raw_styles(component.styles))

        yield cur_styles, component.text

        if component.extra:
            for extra in component.extra:
                yield from _flatten(extra, cur_styles)

    elif isinstance(component, str):
        yield parent_styles, component


def flatten(component: TextComponent) -> list[tuple[dict, str]]:
    return list(_flatten(component))


def convert(text_component: str | TextComponent | dict, bedrock=False) -> Text | None:
    if isinstance(text_component, str):
        spans = spans_from_blocks(blocks_from_text(text_component, bedrock=bedrock))
        # 转换成 rich 的格式
        rich_text = Text()
        for span in spans:
            rich_text.append(span.text, style=Style(**get_raw_styles(span.styles)))

        return rich_text

    # TODO
    elif isinstance(text_component, BaseTextComponent):
        spans = flatten(text_component)
        rich_text = Text()

        for span in spans:
            rich_text.append(span[1], style=Style(**span[0]))

        return rich_text

    else:
        return None
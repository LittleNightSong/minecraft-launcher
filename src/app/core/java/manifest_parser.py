from typing import Any


def parse(data: str):
    result = {}
    last_name = None
    for line in data.splitlines():
        if not line.strip():
            continue

        print(line, line.split(': ', 1))
        strips = line.split(': ', 1)
        if len(strips) == 2:
            last_name = strips[0]
            result[strips[0]] = strips[1]
        elif last_name:
            result[last_name] += line
        else:
            raise ValueError("无法解析的清单")

    return result


def unparse(data: dict[str, Any]):
    lines = []
    for k, v in data.items():
        lines.append(f'{k}: {v}')

    return '\n'.join(lines)

units = (
    'K', 'M', 'G', 'T'
)

base = 1024


def format(size):
    if size < base:
        return str(size)

    else:
        for i, unit in enumerate(units, start=2):
            k = base ** i
            if size < k:
                return f'{size}{unit}'

    return f'{size}{unit}'


def parse(string):
    if not string:
        raise ValueError("Empty string")

    unit = string[-1].upper()

    match unit:
        case 'B':
            assert len(string) > 1
            match string[-2].upper():
                case 'K':
                    return int(string[:-2]) * 1000
                case 'M':
                    return int(string[:-2]) * 1000 * 1000
                case 'G':
                    return int(string[:-2]) * 1000 * 1000 * 1000
                case 'T':
                    return int(string[:-2]) * 1000 * 1000 * 1000 * 1000
                case i if i.isdigit():
                    return int(string[:-2])
                case _:
                    raise ValueError(f"Invalid unit: {string}")

        case 'K':
            return int(string[:-1]) * 1024
        case 'M':
            return int(string[:-1]) * 1024 * 1024
        case 'G':
            return int(string[:-1]) * 1024 * 1024 * 1024
        case 'T':
            return int(string[:-1]) * 1024 * 1024 * 1024 * 1024
        case i if i.isdigit():
            return int(string)
        case _:
            raise ValueError(f"Invalid unit: {string}")

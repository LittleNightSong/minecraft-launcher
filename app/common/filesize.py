suffixes = ('KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB')


def format_filesize(size, base=1024):
    if size == 0:
        return '0 bytes'
    if size == 1:
        return "1 byte"
    elif size < base:
        return f'{size:,} bytes'
    else:
        suffix = suffixes[0]
        unit = base
        for i, suffix in enumerate(suffixes, 2):
            unit = base ** i
            if size < unit:
                break

        return f'{size * base / unit:,.2f} {suffix}'


if __name__ == '__main__':
    print(format_filesize(0))
    print(format_filesize(1))
    print(format_filesize(1024))
    print(format_filesize(1024*1024))
    print(format_filesize(114514))
    print(format_filesize(11451400))

    # "D:\Program Files\uv\uv.exe" run E:/.projects/minecraft-launcher/.venv/Scripts/python.exe E:\.projects\minecraft-launcher\app\common\filesize.py
    # 1.00 KiB
    # 1.00 MiB
    # 111.83 KiB
    # 10.92 MiB
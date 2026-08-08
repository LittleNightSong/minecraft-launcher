import configparser
import subprocess
from pathlib import Path


def get_python_home():
    venv = Path('./.venv')

    parser = configparser.ConfigParser()
    parser.read_string(
        '[DEFAULT]\n' + (venv / 'pyvenv.cfg').read_text()
    )
    data = dict(parser['DEFAULT'])

    home = data['home']
    return home


def pack_python(output=None):
    output = output or 'python.7z'

    home = get_python_home()

    # 将这个目录打包成 7z
    ps = subprocess.run(['7z', 'a', output, home, '-r', '-aoa'])
    if ps.returncode == 0:
        print("成功打包")
    else:
        print("无法打包")


if __name__ == '__main__':
    pack_python()

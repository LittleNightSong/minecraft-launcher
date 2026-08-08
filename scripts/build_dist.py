import shutil
import subprocess
from pathlib import Path

from scripts.build_pyz import main as build_pyz
from scripts.pack_python import get_python_home


def get_project_version():
    ps = subprocess.run(
        ['uv', 'version', '--short'],
        check=True,
        capture_output=True
    )
    return ps.stdout.decode().strip()


def build_dist():
    # 第一步，生成一个分发目录
    build = Path('build').absolute()
    dist = Path('dist').absolute()

    shutil.rmtree(build, ignore_errors=True)  # 清理旧的编译文件
    build.mkdir(parents=True, exist_ok=True)

    # 第二步，找到本地的 python
    home = get_python_home()

    # 第三步，正常生成一个 pyz 分发包
    build_pyz(build / 'clcl.pyz')

    # 第四步，将python移至 .runtime 中
    shutil.copytree(home, build / '.runtime' / 'python', dirs_exist_ok=True, ignore=shutil.ignore_patterns('*.pyc'))
    # 第五步，放入 pyproject 文件
    shutil.copy2('./pyproject.toml', build / 'pyproject.toml')
    # 第六步，放入启动脚本
    shutil.copy2('./scripts/launch.sh', build / 'clcl.sh')
    shutil.copy2('./scripts/launch.cmd', build / 'clcl.cmd')
    shutil.copy2('./scripts/launch.cmd', build / 'clcl.bat')
    shutil.copy2('./scripts/launch.ps1', build / 'clcl.ps1')
    # 第七步，打成一个压缩包
    dist_file = dist / f'clcl-v{get_project_version()}.7z'

    if not dist_file.exists():
        subprocess.run([
            '7z', 'a',
            str(dist_file),

            '-r',

            str('clcl*'),
            str('.runtime'),
            str('pyproject.toml')
        ],
            cwd=build
        )
    else:
        subprocess.call([
            '7z', 'u',
            str(dist_file),

            '-uq0r2x2y2z0',
            '-r',

            str('clcl*'),
            str('.runtime'),
            str('pyproject.toml')
        ],
            cwd=build
        )
    # 完成


if __name__ == '__main__':
    build_dist()

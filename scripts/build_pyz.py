import os.path
import sys
import zipfile
from pathlib import Path

sys.path.append('.')


bootstrap_code = """
import sys
import zipfile
from tqdm import tqdm
from pathlib import Path

c_extensions = {}
unzip_all = {}

def bootstrap():
    sys.path.insert(0, 'site-packages')
    
    # print(sys.argv[0])
    # 自动解压

    self = Path(sys.argv[0])
    runtime_dir = Path(self).parent / '.runtime' / self.stem
    (runtime_dir / 'site-packages').mkdir(parents=True, exist_ok=True)
    
    if runtime_dir.is_dir():
        return
    
    try:
        sys.path.insert(1, str(runtime_dir))
    
        with zipfile.ZipFile(self) as f:
            for file in tqdm(c_extensions):
                f.extract(file, runtime_dir)
            
            if unzip_all:
                for file in f.namelist():
                    # print(file)
                    if file.startswith('site-packages'):
                        f.extract(file, runtime_dir)
    
    except:
        import shutil
        shutil.rmtree(runtime_dir)

# """


def safe_rwrite(w: zipfile.ZipFile, dir, target):
    for dirpath, dirnames, filenames in Path(dir).walk():
        w.mkdir(str(dirpath))
        for f in filenames:
            final_path = os.path.join(target, dirpath.relative_to(dir), f)
            w.write(os.path.join(dirpath, f), final_path)

def main():
    src_dir = './app'
    launch_script = './cli.py'
    output = './clcl.pyz'
    selected_interface = 'commandline'
    site_packages_dir = './.venv/Lib/site-packages'
    unzip_all = False

    with zipfile.ZipFile(output, 'w') as f:
        safe_rwrite(f, os.path.join(src_dir, 'core'), '/app/core')
        safe_rwrite(f, os.path.join(
            src_dir, 'interfaces', selected_interface), f'/app/interfaces/{selected_interface}')
        with f.open('__init__.py', 'w'): ...
        with (
            f.open('__main__.py', 'w') as fw,
            open(launch_script, 'rb') as fr
        ):
            fw.write(
                b"import _bootstrap\n"
                b"_bootstrap.bootstrap()\n"
            )
            fw.write(fr.read())

        # 扫描 site-packages
        c_extensions = []
        for dirpath, _, filenames in Path(site_packages_dir).walk():
            relative_path = Path('site-packages') / dirpath.relative_to(site_packages_dir)

            for i in filenames:
                if i.endswith(('.pyd', '.so')):
                    c_extensions.append(str((relative_path / i).as_posix()))
                    # continue

                elif not i.endswith('.py') and i not in {
                    'INSTALLER', 'METADATA', 'RECORD', 'REQUESTED', 'WHEEL'
                } and dirpath.name != 'licenses':
                    continue

                f.write(
                    str(dirpath / i),
                    str(relative_path / i)
                )


        with f.open('_bootstrap.py', 'w') as f:
            f.write(
                bootstrap_code.format(repr(c_extensions), unzip_all).encode()
            )






if __name__ == '__main__':
    main()

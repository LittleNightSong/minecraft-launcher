import os.path
import sys
import zipfile
from pathlib import Path

sys.path.append('.')

bootstrap_code = """
import sys
import zipfile
from pathlib import Path

self = Path(__file__).parent

def tqdm(data):
    total = len(data)
    for i, item in enumerate(data):
        yield item
        print(f"\\rFix Dependencies {i}/{total}", end='')
    print('\\033[2K')

def bootstrap():
    
    # print(sys.argv[0])
    # 自动解压

    runtime_dir = Path(self).parent / '.runtime' / self.stem
    (runtime_dir / 'site-packages').mkdir(parents=True, exist_ok=True)
    
    try:
        sys.path.insert(0, str(runtime_dir / 'site-packages'))
        
        # print(sys.path)
    
        with zipfile.ZipFile(self) as f:
            # file_needed = [file for file in c_extensions if not (runtime_dir / file).is_file()]
            
            file_needed = [
                file for file in f.namelist() 
                if file.startswith('site-packages') and not (runtime_dir / file).exists()
            ]
            
            if file_needed:
                for file in tqdm(file_needed):
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
        with f.open('__init__.py', 'w'):
            ...
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
                bootstrap_code.encode()
            )


if __name__ == '__main__':
    main()

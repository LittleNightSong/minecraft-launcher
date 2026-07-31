import os
import zipfile
from pathlib import Path

from app.interfaces.commandline.base import console


def safe_write(w: zipfile.ZipFile, file):
    if os.path.isfile(file):
        w.write(file, os.path.basename(file))


def safe_rwrite(w: zipfile.ZipFile, dir):
    if os.path.isdir(dir):
        dirname = os.path.basename(dir)
        for dirpath, dirnames, filenames in Path(dir).walk():
            parent = os.path.join(dirname, dirpath.relative_to(dir))
            w.mkdir(parent)
            for f in filenames:
                final_path = os.path.join(parent, f)
                # console.print({
                #     'dir': dir,
                #     'current_dir': dirpath,
                #     'arc_path': final_path,
                #     'parent_dir': parent,
                # })
                w.write(os.path.join(dirpath, f), final_path)

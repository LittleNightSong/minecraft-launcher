import os
import zipfile


exts_mapping = {
    'nt': ('.dll', '.pdb'),
    'posix': '.so',
    'darwin': '.dylib',
}

def extract_to(archive, target):
    ext_names = exts_mapping[os.name]
    with zipfile.ZipFile(archive) as z:
        for i in z.infolist():
            # print(i.filename)
            if not i.filename.endswith(ext_names):
                # print('skip')
                continue

            # print("extract")
            z.extract(i, target)


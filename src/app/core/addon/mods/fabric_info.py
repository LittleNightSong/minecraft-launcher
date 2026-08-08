import zipfile

import msgspec

from app.core.models.mod import ModMeta


# def parse_


def  get_fabric_info(file):
    with zipfile.ZipFile(file, 'r') as zf:
        manifest = msgspec.json.decode(zf.read('fabric.mod.json'))
        ModMeta(
            id=manifest['id'],
            version=manifest['version'],
            display_name=manifest['name'],
            description=manifest['description'],
            urls=manifest['contact'],
            icon=manifest['icon'],
            environment=manifest['environment'],
        )
import zipfile
from app.core.java.manifest_parser import parse as parse_java_manifest


class JarFile:
    def __init__(self, filename):
        self._fp = zipfile.ZipFile(filename)
        self._manifest = None

    @property
    def manifest(self) -> dict[str, str]:
        if self._manifest is None:
            manifest_content = self._fp.read('META-INF/MANIFEST.MF').decode('utf-8')
            manifest = parse_java_manifest(manifest_content)
            self._manifest = manifest

        return self._manifest

    @property
    def main_class(self) -> str:
        return self.manifest['Main-Class'].strip()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._fp.close()


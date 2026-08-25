from pathlib import Path

from .base import BaseDirectory


class ServerDirectory(BaseDirectory):
    def __init__(self, path):
        self.path = Path(path)

    @property
    def server_file(self):
        return self.path / 'server.jar'

    @property
    def eula_file(self):
        return self.path / 'eula.txt'

    @property
    def server_properties_file(self):
        return self.path / 'server.properties'

    # def agree_eula(self):
    #     self.eula_file.write_text(
    #         re.sub(
    #             r'',
    #             self.eula_file.read_text(),
    #         )
    #     )

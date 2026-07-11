import dataclasses
import json
from uuid import UUID

import msgspec


@dataclasses.dataclass(slots=True, kw_only=True)
class LaunchContext:
    # Basic 
    username: str
    version_name: str
    version_type: str

    user_properties: dict = dataclasses.field(default_factory=dict)
    user_type: str = 'legacy'
    
    # Resources
    game_dir: str
    assets_dir: str
    assets_index_name: str
    
    # Auth
    uuid: str | UUID
    token: str
    clientid: str
    xuid: str
    
    # Customs
    
    # 1. window size
    width: int | None = None
    height: int | None = None
    
    # 2. quick play
    quick_play_path: str | None = None
    
    # for single player
    quick_play_single_player: str | None = None
    
    # for multi-player
    quick_play_multi_player: str | None = None
    
    # for realms
    quick_play_realms: str | None = None

    # 3. JVM Contexts
    natives_dir: str
    classpath: str

    # 4. Launcher info
    launcher_name: str
    launcher_version: str



    def to_dict(self):
        return {
            'auth_player_name': self.username,
            'version_name': self.version_name,
            'version_type': self.version_type,

            'user_type': self.user_type,
            'user_properties': json.dumps(self.user_properties),

            'game_directory': self.game_dir,
            'assets_root': self.assets_dir,
            'assets_index_name': self.assets_index_name,

            'auth_uuid': self.uuid,
            'auth_access_token': self.token,
            'clientid': self.clientid,
            'auth_xuid': self.xuid,

            'resolution_width': self.width,
            'resolution_height': self.height,

            'quick_play_path': self.quick_play_path,
            'quick_play_single_player': self.quick_play_single_player,
            'quick_play_multi_player': self.quick_play_multi_player,
            'quick_play_realms': self.quick_play_realms,

            'natives_directory': self.natives_dir,
            'classpath': self.classpath,

            'launcher_name': self.launcher_name,
            'launcher_version': self.launcher_version,

        }


@dataclasses.dataclass(slots=True, kw_only=True)
class BasicJVMContext:
    memmin: str
    memmax: str
    gc: str = 'ZGC'

    def to_args(self):
        gc_flags = {
            'ZGC': ['-XX:+UseZGC'],
            'G1GC': ['-XX:+UseG1GC'],
            'CMS': ['-XX:+UseConcMarkSweepGC'],
            'Serial': ['-XX:+UseSerialGC'],
            'Parallel': ['-XX:+UseParallelGC'],
        }

        return [
            '-Xms' + self.memmin,
            '-Xmx' + self.memmax,
            *gc_flags.get(self.gc.upper(), [f'-{self.gc}'])
        ]
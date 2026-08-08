import platformdirs

from .errors import *
from .filesize import format_filesize
from .methods import *
from .timer import SimpleStopWatch

app_dirs = platformdirs.PlatformDirs(
    appname="CLCL",
    appauthor="LittleNightSong (LittleNightSongYO@outlook.com)",
    ensure_exists=True
)

import os

from chronomia import Chronomia


chronomia = Chronomia(
    os.environ.get('CHRONOMIA_ENABLED', '0') == '1',
)

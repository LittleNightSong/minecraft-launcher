import hashlib
from os import PathLike

from app.common.concurrent_ import threaded


@threaded
def compute_hash(file, algorithm='sha1', chunk_size=65536):
    hasher = hashlib.new(algorithm)
    with open(file, 'rb') as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)

    return hasher.hexdigest()


async def check_or_callback(file: PathLike[str], hash: str, callback, algorithm='sha1', chunk_size=65536):
    if hash != await compute_hash(file, algorithm, chunk_size):
        callback(file)


async def check_hash(file: PathLike[str], hash: str, algorithm='sha1', chunk_size=65536):
    return hash.lower() == await compute_hash(file, algorithm, chunk_size)
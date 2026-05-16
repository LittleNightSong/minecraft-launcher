import os
from os import PathLike

from app.common import run_in_process

default_chunk_size = 1024 * 1024


def _compute_hash(file, algorithm='sha1', chunk_size=default_chunk_size):
    import hashlib
    hasher = hashlib.new(algorithm)
    with open(file, 'rb') as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)

    return hasher.hexdigest()


async def compute_hash(file, algorithm='sha1', chunk_size=default_chunk_size):
    return await run_in_process(_compute_hash, os.fspath(file), algorithm, chunk_size)


async def check_or_callback(file: PathLike[str], hash: str, callback, algorithm='sha1', chunk_size=default_chunk_size):
    if hash != await compute_hash(file, algorithm, chunk_size):
        callback(file)


async def check_hash(file: PathLike[str], hash: str, algorithm='sha1', chunk_size=default_chunk_size):
    return hash.lower() == await compute_hash(file, algorithm, chunk_size)

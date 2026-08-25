import asyncio
import dataclasses
import pathlib
import subprocess
from pathlib import Path


@dataclasses.dataclass(slots=True)
class ProcessBuilder:
    args: list[str] = dataclasses.field(default_factory=list)
    executable: str | Path = ''

    stdin: int | None = subprocess.PIPE
    stdout: int | None = subprocess.PIPE
    stderr: int | None = subprocess.PIPE

    env: dict[str, str] = dataclasses.field(default_factory=dict)

    creation_flags: int = 0

    cwd: str | pathlib.Path | None = None

    # text: bool = False
    # bufsize: int = -1

    def __iadd__(self, other):
        if isinstance(other, (list, tuple)):
            self.args.extend(other)
            return self

        self.args.append(other)
        return self

    def __lshift__(self, other: Path | str):
        self.executable = other
        return self

    def __ior__(self, other):
        self.cwd = other
        return self

    def __getitem__(self, item):
        return self.env[item]

    def __setitem__(self, key, value):
        self.env[key] = value

    def env_setdefault(self, key, value):
        self.env.setdefault(key, value)

    async def run(self):
        return await asyncio.create_subprocess_exec(
            self.executable,
            *self.args,
            stdin=self.stdin,
            stdout=self.stdout,
            stderr=self.stderr,

            env=self.env,
            # text=self.text,

            # bufsize=self.bufsize
            creationflags=self.creation_flags,

            cwd=self.cwd
        )

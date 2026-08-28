from __future__ import annotations

import os
from pathlib import Path


def acquire_lock(path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            os.kill(int(path.read_text().strip()), 0)
            return False
        except (OSError, ValueError):
            path.unlink(missing_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    return True


def release_lock(path: Path) -> None:
    try:
        if int(path.read_text().strip()) == os.getpid():
            path.unlink(missing_ok=True)
    except (OSError, ValueError):
        pass

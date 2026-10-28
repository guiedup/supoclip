"""Durable replacement without attempting to open directories on Windows."""

import os
from pathlib import Path


def durable_replace(source: Path, target: Path) -> None:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        move = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
        move.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
        move.restype = wintypes.BOOL
        # Replace existing destination and ask Windows to complete disk writes.
        if not move(str(source.resolve()), str(target.resolve()), 0x1 | 0x8):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        source.replace(target)
        fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

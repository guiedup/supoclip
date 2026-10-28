"""Shared/exclusive process locks using flock on Unix and LockFileEx on Windows."""

import errno

import portalocker

LOCK_EX = portalocker.LOCK_EX
LOCK_SH = portalocker.LOCK_SH
LOCK_NB = portalocker.LOCK_NB
LOCK_UN = portalocker.LOCK_UN


def flock(handle, operation):
    try:
        if operation == LOCK_UN:
            portalocker.unlock(handle)
        else:
            portalocker.lock(handle, operation)
    except portalocker.exceptions.AlreadyLocked:
        raise BlockingIOError(errno.EAGAIN, "Media file is leased by another process") from None

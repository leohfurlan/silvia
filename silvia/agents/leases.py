"""Single local runner ownership. Dead processes require explicit resume."""
import os
import ctypes


def alive(owner: str) -> bool:
    try:
        pid = int(owner.split(":")[0])
    except (ValueError, AttributeError):
        return True  # Unknown ownership fails closed.
    if os.name == "nt":
        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return kernel.GetLastError() == 5
        kernel.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

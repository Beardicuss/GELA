from __future__ import annotations

import ctypes
import sys


ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Local\\GelaVoiceAssistant"


class SingleInstanceLock:
    def __init__(self, name: str = MUTEX_NAME, kernel32=None) -> None:
        self.name = name
        self._kernel32 = kernel32
        self._handle = None

    def acquire(self) -> bool:
        if sys.platform != "win32":
            return True
        kernel32 = self._kernel32 or ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        ctypes.set_last_error(0)
        handle = kernel32.CreateMutexW(None, False, self.name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        self._kernel32 = kernel32
        self._handle = handle
        return True

    def close(self) -> None:
        if self._handle is not None and self._kernel32 is not None:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None

    def __enter__(self) -> "SingleInstanceLock":
        if not self.acquire():
            raise RuntimeError("Gela is already running")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

from voice_assistant import single_instance
from voice_assistant.single_instance import ERROR_ALREADY_EXISTS, SingleInstanceLock


class FakeFunction:
    def __init__(self, result=None) -> None:
        self.result = result
        self.calls = []
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        self.calls.append(args)
        return self.result


class FakeKernel32:
    def __init__(self) -> None:
        self.CreateMutexW = FakeFunction(123)
        self.CloseHandle = FakeFunction(True)


def test_first_instance_owns_mutex(monkeypatch) -> None:
    kernel32 = FakeKernel32()
    monkeypatch.setattr(single_instance.sys, "platform", "win32")
    monkeypatch.setattr(single_instance.ctypes, "set_last_error", lambda value: None)
    monkeypatch.setattr(single_instance.ctypes, "get_last_error", lambda: 0)
    lock = SingleInstanceLock(kernel32=kernel32)

    assert lock.acquire() is True
    lock.close()

    assert kernel32.CreateMutexW.calls[0][2] == "Local\\GelaVoiceAssistant"
    assert kernel32.CloseHandle.calls == [(123,)]


def test_second_instance_exits_without_owning_mutex(monkeypatch) -> None:
    kernel32 = FakeKernel32()
    monkeypatch.setattr(single_instance.sys, "platform", "win32")
    monkeypatch.setattr(single_instance.ctypes, "set_last_error", lambda value: None)
    monkeypatch.setattr(single_instance.ctypes, "get_last_error", lambda: ERROR_ALREADY_EXISTS)
    lock = SingleInstanceLock(kernel32=kernel32)

    assert lock.acquire() is False
    assert kernel32.CloseHandle.calls == [(123,)]

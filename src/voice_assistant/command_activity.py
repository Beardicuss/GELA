from __future__ import annotations

from dataclasses import dataclass
import threading
import time

from .remote_commands import RemoteCommandResult


_GEORGIAN_LATIN = str.maketrans({
    "ა":"A", "ბ":"B", "გ":"G", "დ":"D", "ე":"E", "ვ":"V", "ზ":"Z",
    "თ":"T", "ი":"I", "კ":"K", "ლ":"L", "მ":"M", "ნ":"N", "ო":"O",
    "პ":"P", "ჟ":"ZH", "რ":"R", "ს":"S", "ტ":"T", "უ":"U", "ფ":"P",
    "ქ":"K", "ღ":"GH", "ყ":"Q", "შ":"SH", "ჩ":"CH", "ც":"TS", "ძ":"DZ",
    "წ":"TS", "ჭ":"CH", "ხ":"KH", "ჯ":"J", "ჰ":"H",
})


def board_text(value: str | None, limit: int = 34) -> str:
    text = (value or "").translate(_GEORGIAN_LATIN).upper()
    text = " ".join(text.split())
    return "".join(character if 32 <= ord(character) < 127 else "?" for character in text)[:limit]


@dataclass(frozen=True)
class CommandActivity:
    source: str
    transcript: str
    matched_command: str
    result: str
    updated_at: int


class CommandActivityStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: CommandActivity | None = None

    def record(self, source: str, result: RemoteCommandResult) -> None:
        label = {
            "executed": "COMPLETED",
            "not-understood": "COMMAND NOT FOUND",
            "failed": "COMMAND FAILED",
        }.get(result.status, result.status.upper())
        with self._lock:
            self._latest = CommandActivity(
                source=board_text(source, 12),
                transcript=board_text(result.transcript),
                matched_command=board_text(result.matched_command),
                result=label,
                updated_at=int(time.time()),
            )

    def snapshot(self, gela_status: str) -> dict[str, object]:
        with self._lock:
            latest = self._latest
        payload: dict[str, object] = {"gelaStatus": board_text(gela_status, 22)}
        if latest is not None:
            payload.update(
                source=latest.source,
                transcript=latest.transcript,
                matchedCommand=latest.matched_command,
                result=latest.result,
                updatedAt=latest.updated_at,
            )
        return payload

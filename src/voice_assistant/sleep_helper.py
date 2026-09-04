from __future__ import annotations

from datetime import datetime
import time

from .actions import _perform_windows_sleep
from .config import USER_LOG_ROOT


SLEEP_HELPER_LOG = USER_LOG_ROOT / "sleep_helper.log"


def main() -> int:
    time.sleep(1.5)
    try:
        _perform_windows_sleep()
    except Exception as exc:
        SLEEP_HELPER_LOG.parent.mkdir(parents=True, exist_ok=True)
        SLEEP_HELPER_LOG.write_text(
            f"{datetime.now().astimezone().isoformat()} {type(exc).__name__}: {exc}\n",
            encoding="utf-8",
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

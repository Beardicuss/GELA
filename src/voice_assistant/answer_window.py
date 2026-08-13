from __future__ import annotations

import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk

from .local_qa import LAST_ANSWER_PATH


def main(path: Path | None = None) -> int:
    answer_path = path or (Path(sys.argv[1]) if len(sys.argv) > 1 else LAST_ANSWER_PATH)
    try:
        payload = json.loads(answer_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read Gela's answer: {exc}") from exc

    root = tk.Tk()
    root.title(str(payload.get("window_title", "Gela — პასუხი")))
    root.geometry("680x440")
    root.minsize(480, 300)
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="კითხვა", font=("Segoe UI", 10, "bold")).pack(anchor="w")
    ttk.Label(frame, text=str(payload.get("question", "")), wraplength=640).pack(
        anchor="w", pady=(4, 14)
    )
    ttk.Label(frame, text="პასუხი", font=("Segoe UI", 10, "bold")).pack(anchor="w")
    text = tk.Text(frame, wrap="word", font=("Segoe UI", 11), padx=8, pady=8)
    text.insert("1.0", str(payload.get("answer", "")))
    text.configure(state="disabled")
    text.pack(fill="both", expand=True, pady=(4, 12))
    source = str(payload.get("source", "")).strip()
    if source:
        ttk.Label(frame, text=f"წყარო: {source}").pack(anchor="w", pady=(0, 8))

    def copy_answer() -> None:
        root.clipboard_clear()
        root.clipboard_append(str(payload.get("answer", "")))

    buttons = ttk.Frame(frame)
    buttons.pack(fill="x")
    ttk.Button(buttons, text="პასუხის კოპირება", command=copy_answer).pack(side="left")
    ttk.Button(buttons, text="დახურვა", command=root.destroy).pack(side="right")
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

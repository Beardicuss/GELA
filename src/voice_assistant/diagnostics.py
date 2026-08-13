from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

from .audio import find_input_device, verify_input_stream
from .config import PROJECT_ROOT, USER_DATA_ROOT, load_settings
from .runtime_status import read_runtime_status
from .worker import LOG_PATH


FIELDS = (
    ("status", "ასისტენტის მდგომარეობა"),
    ("microphone", "არჩეული მიკროფონი"),
    ("microphone_state", "მიკროფონის მდგომარეობა"),
    ("models", "მეტყველების მოდელები"),
    ("catalog", "აპლიკაციების კატალოგი"),
    ("last_wake", "ბოლო გამოღვიძების შედეგი"),
    ("last_command", "ბოლო ბრძანების შედეგი"),
    ("last_execution", "ბოლო შესრულება"),
    ("updated_at", "ბოლო განახლება"),
)

STATUS_VALUES = {
    "starting": "ირთვება",
    "sleeping": "ძილის რეჟიმი — ველოდები „გელას“",
    "listening_command": "ვისმენ ბრძანებას",
    "listening_question": "ვისმენ კითხვას",
    "answering_question": "ვამზადებ ლოკალურ პასუხს",
    "listening_online_query": "ვისმენ ონლაინ ძიების მოთხოვნას",
    "fetching_online": "ვიღებ ონლაინ შედეგს",
    "executing": "ვასრულებ ბრძანებას",
    "cooldown": "დაყოვნების რეჟიმი",
    "paused": "მოსმენა შეჩერებულია",
    "reloading": "კატალოგი ახლდება",
    "recovering_audio": "მიკროფონის კავშირი აღდგება",
    "calibrating": "მიმდინარეობს კალიბრაცია",
    "recognition_testing": "მიმდინარეობს ამოცნობის ტესტი",
    "error": "შეცდომა",
    "stopped": "გაჩერებულია",
}


def localize_status_value(key: str, value: object) -> str:
    text = str(value)
    if key == "status":
        return STATUS_VALUES.get(text, text)
    exact = {
        "None yet": "ჯერ არ არის",
        "connected and listening": "დაკავშირებულია და უსმენს",
        "Georgian and English models loaded": "ქართული და ინგლისური მოდელები ჩატვირთულია",
        "starting": "ირთვება",
        "stopped": "გაჩერებულია",
    }
    if text in exact:
        return exact[text]
    if text.startswith("Ready — ") and text.endswith(" launchable entries"):
        count = text.removeprefix("Ready — ").removesuffix(" launchable entries")
        return f"მზადაა — {count} გასაშვები ჩანაწერი"
    return text


class DiagnosticsWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.values = {key: tk.StringVar(value="მიუწვდომელია") for key, _ in FIELDS}
        self.test_result = tk.StringVar(value="")
        root.title("Gela — დიაგნოსტიკა")
        root.geometry("760x480")
        root.minsize(640, 420)
        icon_path = PROJECT_ROOT / "assets" / "icons" / "gela_tray.png"
        if icon_path.is_file():
            self.icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, self.icon_image)
        self._build()
        self._refresh()

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        ttk.Label(outer, text="Gela-ს ცოცხალი დიაგნოსტიკა", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 14)
        )
        for row, (key, label) in enumerate(FIELDS, start=1):
            ttk.Label(outer, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=4)
            ttk.Label(outer, textvariable=self.values[key], wraplength=500).grid(
                row=row, column=1, sticky="nw", padx=(14, 0), pady=4
            )
        controls = ttk.Frame(outer)
        controls.grid(row=len(FIELDS) + 1, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        ttk.Button(controls, text="მიკროფონის ტესტი", command=self._test_microphone).pack(side="left")
        ttk.Button(controls, text="ჟურნალის გახსნა", command=self._open_logs).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(controls, text="მონაცემთა საქაღალდე", command=lambda: os.startfile(USER_DATA_ROOT)).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(controls, text="დახურვა", command=self.root.destroy).pack(side="right")
        ttk.Label(outer, textvariable=self.test_result, wraplength=700).grid(
            row=len(FIELDS) + 2, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )

    @staticmethod
    def _open_logs() -> None:
        command = (
            [sys.executable, "--logs-window"]
            if getattr(sys, "frozen", False)
            else [sys.executable, "-m", "voice_assistant.logs_window"]
        )
        subprocess.Popen(command, close_fds=True)

    def _refresh(self) -> None:
        state = read_runtime_status()
        for key, _ in FIELDS:
            self.values[key].set(localize_status_value(key, state.get(key, "მიუწვდომელია")))
        self.root.after(1000, self._refresh)

    def _test_microphone(self) -> None:
        self.test_result.set("მიკროფონი მოწმდება…")
        threading.Thread(target=self._run_microphone_test, daemon=True).start()

    def _run_microphone_test(self) -> None:
        try:
            settings = load_settings()
            index, device = find_input_device(
                settings.audio.device_name_contains,
                fallback_to_default=settings.audio.fallback_to_default_input,
            )
            peak = verify_input_stream(index, settings.audio.sample_rate, settings.audio.channels)
            result = f"მიკროფონი მუშაობს: {device['name']} (სიგნალის პიკი {peak})"
        except Exception as exc:
            result = f"მიკროფონის ტესტი ვერ შესრულდა: {exc}"
        self.root.after(0, lambda: self.test_result.set(result))


def main() -> int:
    root = tk.Tk()
    DiagnosticsWindow(root)
    if "--smoke" in __import__("sys").argv:
        root.update_idletasks()
        root.destroy()
        return 0
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

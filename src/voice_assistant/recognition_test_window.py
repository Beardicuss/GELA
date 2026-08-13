from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from vosk import KaldiRecognizer, Model, SetLogLevel

from .alias_store import AliasStore
from .calibration import capture_audio
from .catalog import normalize_phrase, scan_catalog
from .config import PROJECT_ROOT, load_settings
from .recognizer import RecognitionResult, decode_result
from .vocabulary import probe_missing_words


CAPTURE_SECONDS = 4.0
MIN_PROMOTION_CONFIDENCE = 0.5


def recognize_audio(audio: bytes, model: Model, sample_rate: int) -> RecognitionResult:
    recognizer = KaldiRecognizer(model, sample_rate)
    recognizer.SetWords(True)
    recognizer.AcceptWaveform(audio)
    return decode_result(recognizer.FinalResult())


def promote_recognition_result(
    store: AliasStore,
    app_name: str,
    language: str,
    result: RecognitionResult,
) -> str:
    alias = normalize_phrase(result.text)
    if language not in {"ka", "en"}:
        raise ValueError("მხარდაუჭერელი ენა")
    if app_name not in store.app_names:
        raise ValueError("აირჩიეთ კატალოგში არსებული აპლიკაცია")
    if not alias:
        raise ValueError("ამოცნობილი ტექსტი ცარიელია")
    if result.confidence < MIN_PROMOTION_CONFIDENCE:
        raise ValueError(
            f"სანდოობა ძალიან დაბალია ({result.confidence:.3f}); ჩაწერეთ ახალი ნიმუში"
        )
    missing = probe_missing_words(set(alias.split()), language)
    if missing:
        raise ValueError("Vosk-ის ლექსიკაში არ არის: " + ", ".join(sorted(missing)))
    already_present = any(
        normalize_phrase(existing) == alias
        for existing in store.aliases(app_name, language)
    )
    store.add(app_name, language, alias)
    try:
        store.save()
        scan_catalog()
    except Exception:
        if not already_present:
            store.remove(app_name, language, alias)
            store.save()
        raise
    return alias


class RecognitionTestWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.settings = load_settings()
        self.store = AliasStore()
        self.models: dict[str, Model] = {}
        self.results: dict[str, RecognitionResult] = {}
        self.busy = False

        self.status = tk.StringVar(
            value="დააჭირეთ ჩაწერას და ოთხ წამში წარმოთქვით შესამოწმებელი სიტყვა ან ბრძანება."
        )
        self.ka_text = tk.StringVar(value="ჯერ არ არის შედეგი")
        self.en_text = tk.StringVar(value="ჯერ არ არის შედეგი")
        self.language = tk.StringVar(value="ka")
        self.alias_preview = tk.StringVar(value="—")
        self.app_name = tk.StringVar()

        root.title("Gela — მეტყველების ამოცნობის ტესტი")
        root.geometry("820x590")
        root.minsize(720, 520)
        icon_path = PROJECT_ROOT / "assets" / "icons" / "gela_tray.png"
        if icon_path.is_file():
            self.icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, self.icon_image)
        self._build()
        self.language.trace_add("write", lambda *_: self._update_preview())

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(
            outer,
            text="ქართული და ინგლისური ამოცნობის ტესტი",
            font=("Segoe UI", 17, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "აუდიო არ ინახება. Gela ერთსა და იმავე ნიმუშს ორივე ოფლაინ მოდელით "
                "ამოწმებს და აჩვენებს მინიმალურ სიტყვიერ სანდოობას."
            ),
            wraplength=770,
        ).pack(anchor="w", pady=(5, 14))

        controls = ttk.Frame(outer)
        controls.pack(fill="x")
        self.record_button = ttk.Button(controls, text="ჩაწერა — 4 წამი", command=self._record)
        self.record_button.pack(side="left")
        ttk.Label(controls, textvariable=self.status, wraplength=600).pack(
            side="left", padx=(14, 0)
        )

        results = ttk.Frame(outer)
        results.pack(fill="x", pady=14)
        results.columnconfigure(0, weight=1)
        results.columnconfigure(1, weight=1)
        self._result_panel(results, 0, "ქართული მოდელი", self.ka_text, "ka")
        self._result_panel(results, 1, "ინგლისური მოდელი", self.en_text, "en")

        promote = ttk.LabelFrame(outer, text="ამოცნობილი შედეგის ხმოვან სახელად დამატება", padding=14)
        promote.pack(fill="both", expand=True)
        promote.columnconfigure(1, weight=1)
        ttk.Label(promote, text="აპლიკაცია ან თამაში:").grid(row=0, column=0, sticky="w", pady=6)
        self.app_box = ttk.Combobox(
            promote,
            textvariable=self.app_name,
            values=self.store.app_names,
            width=52,
        )
        self.app_box.grid(row=0, column=1, sticky="ew", padx=(14, 0), pady=6)
        ttk.Label(promote, text="დასამატებელი სახელი:").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Label(
            promote,
            textvariable=self.alias_preview,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=1, column=1, sticky="w", padx=(14, 0), pady=6)
        ttk.Label(
            promote,
            text=(
                "დამატებამდე მოწმდება სანდოობა, Vosk-ის ლექსიკა, აპლიკაციების კატალოგი "
                "და სხვა აპლიკაციასთან სახელის კონფლიქტი."
            ),
            wraplength=720,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 12))
        self.promote_button = ttk.Button(
            promote,
            text="არჩეული შედეგის დამატება და გამოყენება",
            command=self._promote,
        )
        self.promote_button.grid(row=3, column=0, columnspan=2, sticky="e")
        self.promote_button.state(["disabled"])

        ttk.Button(outer, text="დახურვა", command=self.root.destroy).pack(anchor="e", pady=(14, 0))

    def _result_panel(
        self,
        parent: ttk.Frame,
        column: int,
        title: str,
        variable: tk.StringVar,
        language: str,
    ) -> None:
        frame = ttk.LabelFrame(parent, text=title, padding=12)
        frame.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=(0, 6) if column == 0 else (6, 0),
        )
        ttk.Label(frame, textvariable=variable, wraplength=340).pack(anchor="w", fill="x")
        ttk.Radiobutton(
            frame,
            text="ამ შედეგის არჩევა",
            variable=self.language,
            value=language,
        ).pack(anchor="w", pady=(10, 0))

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.record_button.state(["disabled"] if busy else ["!disabled"])
        if busy or not self.results:
            self.promote_button.state(["disabled"])
        else:
            self.promote_button.state(["!disabled"])

    def _record(self) -> None:
        if self.busy:
            return
        self._set_busy(True)
        self.status.set("მოდელები მზადდება; შემდეგ ოთხი წამი გისმენთ…")

        def work() -> None:
            try:
                if not self.models:
                    SetLogLevel(-1)
                    self.models = {
                        language: Model(str(self.settings.models[language]))
                        for language in ("ka", "en")
                    }
                audio, _level = capture_audio(CAPTURE_SECONDS)
                results = {
                    language: recognize_audio(
                        audio,
                        self.models[language],
                        self.settings.audio.sample_rate,
                    )
                    for language in ("ka", "en")
                }
            except Exception as exc:
                self.root.after(0, lambda error=exc: self._record_failed(error))
            else:
                self.root.after(0, lambda: self._record_finished(results))

        threading.Thread(target=work, name="gela-recognition-capture", daemon=True).start()

    def _record_failed(self, exc: Exception) -> None:
        self._set_busy(False)
        self.status.set(f"ტესტი ვერ შესრულდა: {exc}")

    def _record_finished(self, results: dict[str, RecognitionResult]) -> None:
        self.results = results
        self.ka_text.set(self._format_result(results["ka"]))
        self.en_text.set(self._format_result(results["en"]))
        self._set_busy(False)
        self._update_preview()
        self.status.set("ორივე ოფლაინ მოდელის შედეგი მზადაა.")

    @staticmethod
    def _format_result(result: RecognitionResult) -> str:
        text = result.text or "[არაფერი]"
        return f"{text}\nსანდოობა: {result.confidence:.3f}"

    def _update_preview(self) -> None:
        result = self.results.get(self.language.get())
        self.alias_preview.set(result.text if result and result.text else "—")

    def _promote(self) -> None:
        if self.busy:
            return
        language = self.language.get()
        result = self.results.get(language)
        if result is None:
            return
        app_name = self.app_name.get().strip()
        self._set_busy(True)
        self.status.set("სახელი მოწმდება და კატალოგს ემატება…")

        def work() -> None:
            try:
                alias = promote_recognition_result(self.store, app_name, language, result)
            except Exception as exc:
                self.root.after(0, lambda error=exc: self._promotion_failed(error))
            else:
                self.root.after(0, lambda: self._promotion_finished(alias, app_name))

        threading.Thread(target=work, name="gela-alias-promotion", daemon=True).start()

    def _promotion_failed(self, exc: Exception) -> None:
        self._set_busy(False)
        self.status.set("სახელი არ დამატებულა.")
        messagebox.showerror("სახელის დამატება ვერ მოხერხდა", str(exc))

    def _promotion_finished(self, alias: str, app_name: str) -> None:
        self._set_busy(False)
        self.status.set(f"„{alias}“ დაემატა აპლიკაციას: {app_name}")
        messagebox.showinfo("Gela", "ხმოვანი სახელი შენახულია და გამოყენებულია.")


def main() -> int:
    root = tk.Tk()
    RecognitionTestWindow(root)
    if "--smoke" in __import__("sys").argv:
        root.update_idletasks()
        root.destroy()
        return 0
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

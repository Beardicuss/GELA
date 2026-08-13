from __future__ import annotations

from array import array
import json
import math
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import sounddevice as sd
from vosk import KaldiRecognizer, Model, SetLogLevel

from .audio import find_input_device
from .catalog import normalize_phrase
from .config import DEFAULT_CONFIG_PATH, PROJECT_ROOT, load_settings
from .recognizer import RecognitionResult, decode_result
from .storage import atomic_write_text


REQUIRED_SAMPLES = 5


def _rms(data: bytes) -> float:
    samples = array("h")
    samples.frombytes(data)
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def capture_audio(duration_seconds: float) -> tuple[bytes, float]:
    settings = load_settings()
    index, _ = find_input_device(
        settings.audio.device_name_contains,
        fallback_to_default=settings.audio.fallback_to_default_input,
    )
    blocks = max(1, math.ceil(duration_seconds * settings.audio.sample_rate / settings.audio.block_size))
    chunks: list[bytes] = []
    levels: list[float] = []
    with sd.RawInputStream(
        device=index,
        samplerate=settings.audio.sample_rate,
        channels=1,
        dtype="int16",
        blocksize=settings.audio.block_size,
    ) as stream:
        for _ in range(blocks):
            data, _ = stream.read(settings.audio.block_size)
            chunk = bytes(data)
            chunks.append(chunk)
            levels.append(_rms(chunk))
    return b"".join(chunks), sum(levels) / len(levels)


def recognize_wake_sample(audio: bytes, model: Model) -> RecognitionResult:
    settings = load_settings()
    recognizer = KaldiRecognizer(model, settings.audio.sample_rate)
    recognizer.SetWords(True)
    recognizer.AcceptWaveform(audio)
    return decode_result(recognizer.FinalResult())


def recommend_calibration(
    ambient_rms: float,
    samples: list[RecognitionResult],
    wake_phrase: str,
) -> tuple[float, int] | None:
    wake_phrase = normalize_phrase(wake_phrase)
    correct = [sample.confidence for sample in samples if sample.text == wake_phrase]
    if len(correct) < 3:
        return None
    wake_confidence = round(max(0.85, min(0.95, min(correct) - 0.03)), 2)
    vad_min_rms = round(max(180, min(8_000, ambient_rms * 2.5)))
    return wake_confidence, vad_min_rms


def apply_calibration(
    wake_confidence: float,
    vad_min_rms: int,
    path=DEFAULT_CONFIG_PATH,
) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["background"]["wake_confidence"] = wake_confidence
    raw["background"]["vad_min_rms"] = vad_min_rms
    atomic_write_text(path, json.dumps(raw, ensure_ascii=False, indent=2) + "\n")


class CalibrationWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.settings = load_settings()
        self.wake_phrase = self.settings.background.wake_phrases[0]
        self.ambient_rms: float | None = None
        self.samples: list[RecognitionResult] = []
        self.model: Model | None = None
        self.busy = False
        self.status = tk.StringVar(value="დაიწყეთ ოთახის ხმაურის სამწამიანი გაზომვით.")
        self.noise = tk.StringVar(value="არ არის გაზომილი")
        self.progress = tk.StringVar(value=f"0 / {REQUIRED_SAMPLES} ნიმუში")
        self.recommendation = tk.StringVar(value="ჯერ მზად არ არის")

        root.title("Gela — გამაღვიძებელი სიტყვის კალიბრაცია")
        root.geometry("680x480")
        root.minsize(600, 430)
        icon_path = PROJECT_ROOT / "assets" / "icons" / "gela_tray.png"
        if icon_path.is_file():
            self.icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, self.icon_image)
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="„გელას“ კალიბრაცია", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="ეს ოსტატი ჩანაწერებს არ ინახავს. შეინარჩუნეთ ოთახის ჩვეულებრივი სიჩუმე და ილაპარაკეთ ბუნებრივად.",
            wraplength=630,
        ).pack(anchor="w", pady=(6, 16))

        noise_frame = ttk.LabelFrame(outer, text="1. ოთახის ხმაური", padding=12)
        noise_frame.pack(fill="x")
        ttk.Label(noise_frame, textvariable=self.noise).pack(side="left")
        self.noise_button = ttk.Button(noise_frame, text="ხმაურის გაზომვა", command=self._measure_noise)
        self.noise_button.pack(side="right")

        sample_frame = ttk.LabelFrame(outer, text="2. გამაღვიძებელი სიტყვის ნიმუშები", padding=12)
        sample_frame.pack(fill="both", expand=True, pady=12)
        ttk.Label(sample_frame, text=f"„ჩაწერის“ დაჭერის შემდეგ თქვით მხოლოდ „{self.wake_phrase}“.").pack(anchor="w")
        ttk.Label(sample_frame, textvariable=self.progress).pack(anchor="w", pady=(6, 4))
        self.results = tk.Listbox(sample_frame, height=6)
        self.results.pack(fill="both", expand=True)
        self.record_button = ttk.Button(sample_frame, text="ნიმუშის ჩაწერა", command=self._record_sample)
        self.record_button.pack(anchor="e", pady=(8, 0))

        result_frame = ttk.LabelFrame(outer, text="3. რეკომენდაცია", padding=12)
        result_frame.pack(fill="x")
        ttk.Label(result_frame, textvariable=self.recommendation, wraplength=610).pack(anchor="w")
        self.apply_button = ttk.Button(result_frame, text="რეკომენდაციის გამოყენება", command=self._apply)
        self.apply_button.pack(anchor="e", pady=(8, 0))
        self.apply_button.state(["disabled"])

        ttk.Label(outer, textvariable=self.status, wraplength=630).pack(anchor="w", pady=(12, 0))

    def _run(self, task, finished) -> None:
        if self.busy:
            return
        self.busy = True
        self.noise_button.state(["disabled"])
        self.record_button.state(["disabled"])

        def work() -> None:
            try:
                result = task()
            except Exception as exc:
                self.root.after(0, lambda: self._finish_error(exc))
            else:
                self.root.after(0, lambda: self._finish_success(finished, result))

        threading.Thread(target=work, daemon=True).start()

    def _finish_success(self, finished, result) -> None:
        self.busy = False
        self.noise_button.state(["!disabled"])
        self.record_button.state(["!disabled"])
        finished(result)

    def _finish_error(self, exc: Exception) -> None:
        self.busy = False
        self.noise_button.state(["!disabled"])
        self.record_button.state(["!disabled"])
        self.status.set(f"კალიბრაციის შეცდომა: {exc}")

    def _measure_noise(self) -> None:
        self.status.set("შეინარჩუნეთ სიჩუმე, სანამ Gela ოთახის ხმაურს ზომავს…")
        self._run(lambda: capture_audio(3.0)[1], self._noise_measured)

    def _noise_measured(self, level: float) -> None:
        self.ambient_rms = level
        self.noise.set(f"ოთახის საშუალო დონე: {level:.1f} RMS")
        self.status.set("ხმაური გაზომილია. ჩაწერეთ გამაღვიძებელი სიტყვის ხუთი ბუნებრივი ნიმუში.")
        self._update_recommendation()

    def _record_sample(self) -> None:
        if len(self.samples) >= REQUIRED_SAMPLES:
            self.status.set("ხუთივე ნიმუში უკვე ჩაწერილია. გამოიყენეთ შედეგი ან დახურეთ ფანჯარა.")
            return
        self.status.set(f"გისმენთ — თქვით მხოლოდ „{self.wake_phrase}“…")

        def capture() -> RecognitionResult:
            if self.model is None:
                SetLogLevel(-1)
                self.model = Model(str(self.settings.models[self.settings.background.language]))
            audio, _ = capture_audio(2.5)
            return recognize_wake_sample(audio, self.model)

        self._run(capture, self._sample_recorded)

    def _sample_recorded(self, result: RecognitionResult) -> None:
        self.samples.append(result)
        recognized = result.text or "[არაფერი]"
        correct = normalize_phrase(result.text) == normalize_phrase(self.wake_phrase)
        marker = "სწორია" if correct else "არ დაემთხვა"
        self.results.insert(tk.END, f"{len(self.samples)}. {recognized} — {result.confidence:.3f} — {marker}")
        self.progress.set(f"{len(self.samples)} / {REQUIRED_SAMPLES} ნიმუში")
        self.status.set("ნიმუში ჩაწერილია." if correct else "ეს ნიმუში გამაღვიძებელ სიტყვად ვერ ამოიცნო.")
        self._update_recommendation()

    def _update_recommendation(self) -> None:
        if self.ambient_rms is None or len(self.samples) < REQUIRED_SAMPLES:
            self.recommendation.set("გაზომეთ ხმაური და ჩაწერეთ ხუთივე ნიმუში.")
            self.apply_button.state(["disabled"])
            return
        recommendation = recommend_calibration(self.ambient_rms, self.samples, self.wake_phrase)
        if recommendation is None:
            self.recommendation.set("„გელას“ სამზე ნაკლები ნიმუში დაემთხვა. დახურეთ და უფრო წყნარ ადგილას სცადეთ.")
            self.apply_button.state(["disabled"])
            return
        confidence, vad = recommendation
        self.recommendation.set(f"გამოღვიძების სანდოობა: {confidence:.2f}    ხმის მინიმალური დონე: {vad} RMS")
        self.apply_button.state(["!disabled"])

    def _apply(self) -> None:
        recommendation = recommend_calibration(self.ambient_rms or 0.0, self.samples, self.wake_phrase)
        if recommendation is None:
            return
        apply_calibration(*recommendation)
        messagebox.showinfo("Gela", "კალიბრაცია შენახულია. ამ ფანჯრის დახურვის შემდეგ Gela პარამეტრებს თავიდან ჩატვირთავს.")
        self.root.destroy()


def main() -> int:
    root = tk.Tk()
    CalibrationWindow(root)
    if "--smoke" in __import__("sys").argv:
        root.update_idletasks()
        root.destroy()
        return 0
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

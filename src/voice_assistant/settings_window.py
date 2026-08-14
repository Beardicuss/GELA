from __future__ import annotations

import json
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from .audio import input_device_choices, selected_input_device_name
from .config import DEFAULT_CONFIG_PATH, PROJECT_ROOT, load_settings
from .storage import atomic_write_text


class SettingsWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.raw = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        audio = self.raw["audio"]
        background = self.raw["background"]
        catalog = self.raw["catalog"]
        qa = self.raw["question_answering"]
        online = self.raw["online_services"]

        self.wake_phrase = tk.StringVar(value=background["wake_phrases"][0])
        self.command_retries = tk.StringVar(value=str(background["command_retry_attempts"]))
        self.one_sentence_commands = tk.BooleanVar(
            value=background.get("one_sentence_commands", False)
        )
        self.catalog_refresh = tk.BooleanVar(value=catalog["auto_refresh"])
        self.catalog_hours = tk.StringVar(value=f"{catalog['interval_seconds'] / 3600:g}")
        self.microphone = tk.StringVar(value=audio["device_name_contains"])
        self.microphone_choices = []
        self.default_microphone = tk.BooleanVar(value=audio["fallback_to_default_input"])
        self.vad_min_rms = tk.StringVar(value=str(background["vad_min_rms"]))
        self.wake_confidence = tk.StringVar(value=str(background["wake_confidence"]))
        self.command_confidence = tk.StringVar(value=str(background["command_confidence"]))
        self.command_timeout = tk.StringVar(value=str(background["command_timeout_seconds"]))
        self.local_qa = tk.BooleanVar(value=qa["enabled"])
        self.local_model = tk.StringVar(value=qa["model"])
        self.local_endpoint = tk.StringVar(value=qa["endpoint"])
        self.weather = tk.BooleanVar(value=online["weather_enabled"])
        self.wikipedia = tk.BooleanVar(value=online["wikipedia_enabled"])
        self.location = tk.StringVar(value=online["location_name"])
        self.latitude = tk.StringVar(value=str(online["latitude"]))
        self.longitude = tk.StringVar(value=str(online["longitude"]))

        root.title("Gela — პარამეტრები")
        root.geometry("760x610")
        root.minsize(680, 560)
        icon_path = PROJECT_ROOT / "assets" / "icons" / "gela_tray.png"
        if icon_path.is_file():
            self.icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, self.icon_image)
        self._build()

    @staticmethod
    def _row(parent, row: int, label: str, variable: tk.Variable, width: int = 32) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=variable, width=width).grid(
            row=row, column=1, sticky="ew", padx=(16, 0), pady=6
        )

    def _tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(notebook, padding=18)
        frame.columnconfigure(1, weight=1)
        return frame

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Gela-ს პარამეტრები", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="ცვლილებები მოწმდება შენახვამდე და შემდეგ Gela ავტომატურად გადაიტვირთება.",
        ).pack(anchor="w", pady=(4, 12))
        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)

        general = self._tab(notebook)
        notebook.add(general, text="ძირითადი")
        self._row(general, 0, "გამაღვიძებელი სიტყვა", self.wake_phrase)
        ttk.Label(general, text="ბრძანების განმეორების რაოდენობა").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Combobox(general, textvariable=self.command_retries, values=("0", "1", "2", "3"), state="readonly", width=8).grid(row=1, column=1, sticky="w", padx=(16, 0), pady=6)
        ttk.Checkbutton(
            general,
            text="ერთ წინადადებაში ბრძანებები — „გელა გახსენი ქრომი“",
            variable=self.one_sentence_commands,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Checkbutton(general, text="კატალოგის ავტომატური განახლება", variable=self.catalog_refresh).grid(row=3, column=0, columnspan=2, sticky="w", pady=8)
        self._row(general, 4, "განახლების ინტერვალი (საათი)", self.catalog_hours)

        audio = self._tab(notebook)
        notebook.add(audio, text="მიკროფონი")
        ttk.Label(audio, text="არჩეული მიკროფონი").grid(row=0, column=0, sticky="w", pady=6)
        microphone_controls = ttk.Frame(audio)
        microphone_controls.grid(row=0, column=1, sticky="ew", padx=(16, 0), pady=6)
        microphone_controls.columnconfigure(0, weight=1)
        self.microphone_box = ttk.Combobox(
            microphone_controls,
            textvariable=self.microphone,
            state="readonly",
            width=42,
        )
        self.microphone_box.grid(row=0, column=0, sticky="ew")
        ttk.Button(
            microphone_controls,
            text="განახლება",
            command=self._refresh_microphones,
        ).grid(row=0, column=1, padx=(8, 0))
        ttk.Checkbutton(audio, text="სისტემის ნაგულისხმევ მიკროფონზე გადართვა, თუ არჩეული მიუწვდომელია", variable=self.default_microphone).grid(row=1, column=0, columnspan=2, sticky="w", pady=8)
        self._row(audio, 2, "ხმის მინიმალური დონე (RMS)", self.vad_min_rms)
        ttk.Label(audio, text="ზუსტი მნიშვნელობის დასადგენად გამოიყენეთ გამაღვიძებელი სიტყვის კალიბრაცია.", wraplength=620).grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self._refresh_microphones()

        recognition = self._tab(notebook)
        notebook.add(recognition, text="ამოცნობა")
        self._row(recognition, 0, "გამოღვიძების სანდოობა (0–1)", self.wake_confidence)
        self._row(recognition, 1, "ბრძანების სანდოობა (0–1)", self.command_confidence)
        self._row(recognition, 2, "ბრძანების მოლოდინი (წამი)", self.command_timeout)
        ttk.Label(recognition, text="მაღალი სანდოობა ამცირებს შემთხვევით ამოქმედებას, მაგრამ შეიძლება ჩუმი ნათქვამი გამოტოვოს.", wraplength=620).grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))

        services = self._tab(notebook)
        notebook.add(services, text="სერვისები")
        ttk.Checkbutton(services, text="ლოკალური კითხვებზე პასუხი", variable=self.local_qa).grid(row=0, column=0, columnspan=2, sticky="w", pady=5)
        self._row(services, 1, "ლოკალური მოდელი", self.local_model)
        self._row(services, 2, "ლოკალური მისამართი", self.local_endpoint, 42)
        ttk.Separator(services).grid(row=3, column=0, columnspan=2, sticky="ew", pady=12)
        ttk.Checkbutton(services, text="ონლაინ ამინდი", variable=self.weather).grid(row=4, column=0, sticky="w", pady=5)
        ttk.Checkbutton(services, text="ვიკიპედიის ძიება", variable=self.wikipedia).grid(row=4, column=1, sticky="w", padx=(16, 0), pady=5)
        self._row(services, 5, "ამინდის მდებარეობა", self.location)
        self._row(services, 6, "გრძედი (Latitude)", self.latitude)
        self._row(services, 7, "განედი (Longitude)", self.longitude)
        ttk.Label(services, text="ონლაინ სერვისები მხოლოდ პირდაპირი ბრძანების შემდეგ უკავშირდება ინტერნეტს.", wraplength=620).grid(row=8, column=0, columnspan=2, sticky="w", pady=(10, 0))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="გაუქმება", command=self.root.destroy).pack(side="right")
        ttk.Button(buttons, text="შენახვა", command=self._save).pack(side="right", padx=(0, 8))

    def _refresh_microphones(self) -> None:
        try:
            choices = input_device_choices()
        except Exception as exc:
            messagebox.showerror("მიკროფონის შეცდომა", str(exc))
            return
        self.microphone_choices = choices
        names = [choice.name for choice in choices]
        self.microphone_box.configure(values=names)
        selected = selected_input_device_name(self.microphone.get(), choices)
        self.microphone.set(selected)
        self.microphone_box.configure(state="readonly" if names else "disabled")

    def _save(self) -> None:
        try:
            wake = self.wake_phrase.get().strip()
            if not wake:
                raise ValueError("გამაღვიძებელი სიტყვა ცარიელი ვერ იქნება")
            audio = self.raw["audio"]
            background = self.raw["background"]
            catalog = self.raw["catalog"]
            qa = self.raw["question_answering"]
            online = self.raw["online_services"]
            current_choices = input_device_choices()
            selected_microphone = selected_input_device_name(
                self.microphone.get(),
                current_choices,
            )
            if not selected_microphone:
                raise ValueError("Windows-ში ხელმისაწვდომი მიკროფონი ვერ მოიძებნა")
            background.update(
                wake_phrases=[wake],
                one_sentence_commands=self.one_sentence_commands.get(),
                command_retry_attempts=int(self.command_retries.get()),
                vad_min_rms=int(self.vad_min_rms.get()),
                wake_confidence=float(self.wake_confidence.get()),
                command_confidence=float(self.command_confidence.get()),
                command_timeout_seconds=float(self.command_timeout.get()),
            )
            audio.update(device_name_contains=selected_microphone, fallback_to_default_input=self.default_microphone.get())
            catalog.update(auto_refresh=self.catalog_refresh.get(), interval_seconds=float(self.catalog_hours.get()) * 3600)
            qa.update(enabled=self.local_qa.get(), model=self.local_model.get().strip(), endpoint=self.local_endpoint.get().strip())
            online.update(weather_enabled=self.weather.get(), wikipedia_enabled=self.wikipedia.get(), location_name=self.location.get().strip(), latitude=float(self.latitude.get()), longitude=float(self.longitude.get()))
            validation_path = DEFAULT_CONFIG_PATH.with_suffix(".validation.json")
            validation_path.write_text(json.dumps(self.raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            try:
                load_settings(validation_path)
            finally:
                validation_path.unlink(missing_ok=True)
            atomic_write_text(DEFAULT_CONFIG_PATH, json.dumps(self.raw, ensure_ascii=False, indent=2) + "\n")
        except Exception as exc:
            messagebox.showerror("პარამეტრების შეცდომა", str(exc))
            return
        messagebox.showinfo("Gela", "პარამეტრები შენახულია.")
        self.root.destroy()


def main() -> int:
    root = tk.Tk()
    SettingsWindow(root)
    if "--smoke" in sys.argv:
        root.update_idletasks()
        root.destroy()
        return 0
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .alias_manager import windows_unicode_key
from .dictation_corrections import (
    DictationCorrection,
    load_corrections,
    save_corrections,
    validate_corrections,
)
from .notes_theme import CRIMSON, CRIMSON_BORDER, CRIMSON_DIM, CRIMSON_SOFT, SURFACE, SURFACE_DEEP, TEXT, TEXT_MUTED


class DictationCorrectionsPanel(ttk.Frame):
    def __init__(self, master, font_family: str) -> None:
        super().__init__(master, padding=14, style="Cardinal.Panel.TFrame")
        self.font_family = font_family
        self.corrections = load_corrections()
        self.selected: int | None = None
        self.heard_var = tk.StringVar()
        self.replacement_var = tk.StringVar()
        self.status_var = tk.StringVar(value="მონიშნეთ შეცდომა ჩანაწერში ან დაამატეთ ფრაზა აქ.")
        self._build()
        self._refresh()

    def _build(self) -> None:
        ttk.Label(self, text="02  DICTATION MEMORY", style="Cardinal.Kicker.TLabel").pack(anchor="w")
        self.title_label = ttk.Label(self, text="ქართული კარნახის შესწორებები", style="Cardinal.Panel.TLabel", font=(self.font_family, 16, "bold"))
        self.title_label.pack(anchor="w", pady=(4, 0))
        ttk.Label(self, text="ცვლილება შემდეგივე ნაკარნახევი წინადადებიდან მოქმედებს.", style="Cardinal.PanelMuted.TLabel").pack(anchor="w", pady=(3, 10))

        area = ttk.Frame(self, style="Cardinal.Panel.TFrame")
        area.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(area, exportselection=False, font=(self.font_family, 11), background=SURFACE_DEEP, foreground=TEXT, selectbackground=CRIMSON_DIM, selectforeground=TEXT, highlightbackground=CRIMSON_BORDER, highlightcolor=CRIMSON, relief="flat", borderwidth=1, activestyle="none")
        scroll = ttk.Scrollbar(area, orient="vertical", command=self.listbox.yview, style="Cardinal.Vertical.TScrollbar")
        self.listbox.configure(yscrollcommand=scroll.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.listbox.bind("<<ListboxSelect>>", self._selected)

        form = ttk.Frame(self, style="Cardinal.Panel.TFrame")
        form.pack(fill="x", pady=(10, 0))
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Gela-მ გაიგო", style="Cardinal.PanelMuted.TLabel").grid(row=0, column=0, sticky="w", pady=4)
        self.heard_entry = ttk.Entry(form, textvariable=self.heard_var, style="Cardinal.TEntry")
        self.heard_entry.grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(form, text="უნდა დაწეროს", style="Cardinal.PanelMuted.TLabel").grid(row=1, column=0, sticky="w", pady=4)
        self.replacement_entry = ttk.Entry(form, textvariable=self.replacement_var, style="Cardinal.TEntry")
        self.replacement_entry.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=4)
        for entry in (self.heard_entry, self.replacement_entry):
            entry.bind("<KeyPress>", lambda event, widget=entry: self._insert_key(event, widget), add=True)

        buttons = ttk.Frame(self, style="Cardinal.Panel.TFrame")
        buttons.pack(fill="x", pady=(9, 0))
        ttk.Label(buttons, textvariable=self.status_var, style="Cardinal.PanelMuted.TLabel").pack(side="left", fill="x", expand=True)
        ttk.Button(buttons, text="ახალი", command=self.new, style="Cardinal.TButton").pack(side="right")
        ttk.Button(buttons, text="წაშლა", command=self.delete, style="Cardinal.TButton").pack(side="right", padx=6)
        ttk.Button(buttons, text="დამატება / განახლება", command=self.upsert, style="Cardinal.TButton").pack(side="right")
        ttk.Button(self, text="შენახვა და გამოყენება", command=self.save, style="Cardinal.Primary.TButton").pack(anchor="e", pady=(9, 0))

    def apply_font_scale(self, scale: float) -> None:
        self.title_label.configure(font=(self.font_family, round(16 * scale), "bold"))
        self.listbox.configure(font=(self.font_family, round(11 * scale)))

    @staticmethod
    def _insert_key(event, entry) -> str | None:
        character = windows_unicode_key(int(event.keycode))
        if character is None:
            return None
        try:
            entry.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pass
        entry.insert(tk.INSERT, character)
        return "break"

    def _refresh(self) -> None:
        self.listbox.delete(0, tk.END)
        for item in self.corrections:
            self.listbox.insert(tk.END, f"{item.heard}  →  {item.replacement}")

    def _selected(self, _event=None) -> None:
        selection = self.listbox.curselection()
        if selection:
            self.selected = selection[0]
            item = self.corrections[self.selected]
            self.heard_var.set(item.heard)
            self.replacement_var.set(item.replacement)

    def prefill(self, heard: str) -> None:
        self.new()
        self.heard_var.set(" ".join(heard.split()))
        self.replacement_entry.focus_set()
        self.status_var.set("შეიყვანეთ სწორი ფორმა და დაამატეთ შესწორება.")

    def new(self) -> None:
        self.selected = None
        self.listbox.selection_clear(0, tk.END)
        self.heard_var.set("")
        self.replacement_var.set("")

    def upsert(self) -> None:
        item = DictationCorrection(self.heard_var.get().strip(), self.replacement_var.get().strip())
        updated = list(self.corrections)
        if self.selected is None:
            updated.append(item)
        else:
            updated[self.selected] = item
        try:
            validate_corrections(updated)
        except ValueError as exc:
            messagebox.showerror("შესწორება ვერ დაემატა", str(exc), parent=self)
            return
        self.corrections = updated
        self._refresh()
        self.status_var.set("მზადაა შესანახად.")

    def delete(self) -> None:
        if self.selected is not None:
            del self.corrections[self.selected]
            self.new()
            self._refresh()

    def save(self) -> None:
        try:
            save_corrections(self.corrections)
            self.corrections = load_corrections()
        except (OSError, ValueError) as exc:
            messagebox.showerror("შენახვა ვერ მოხერხდა", str(exc), parent=self)
            return
        self._refresh()
        self.status_var.set("შენახულია და უკვე მოქმედებს.")
        messagebox.showinfo("Gela", "კარნახის შესწორებები შენახულია.", parent=self)

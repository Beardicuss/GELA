from __future__ import annotations

import tkinter as tk
from tkinter import ttk


# Shared with the Cardinal mobile theme (src/theme.ts).
BG = "#0a0a0b"
SURFACE = "#111114"
SURFACE_DEEP = "#0d0d10"
SURFACE_WARM = "#141010"
CRIMSON = "#c8392b"
CRIMSON_SOFT = "#e05a4a"
CRIMSON_DIM = "#632c27"
CRIMSON_BORDER = "#34201f"
AMBER = "#d4712a"
TEXT = "#e2ddd8"
TEXT_SECONDARY = "#aaa5a1"
TEXT_MUTED = "#736f6d"
DANGER = "#ff7770"


def configure_cardinal_theme(root: tk.Misc, font_family: str, scale: float = 1.0) -> ttk.Style:
    body_size = round(10 * scale)
    title_size = round(22 * scale)
    kicker_size = round(9 * scale)
    status_size = round(10 * scale)
    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(background=BG)

    common = {"font": (font_family, body_size), "background": BG, "foreground": TEXT}
    style.configure(".", **common)
    style.configure("Cardinal.TFrame", background=BG)
    style.configure("Cardinal.Panel.TFrame", background=SURFACE)
    style.configure("Cardinal.Warm.TFrame", background=SURFACE_WARM)
    style.configure("Cardinal.TLabel", background=BG, foreground=TEXT)
    style.configure("Cardinal.Panel.TLabel", background=SURFACE, foreground=TEXT)
    style.configure("Cardinal.Muted.TLabel", background=BG, foreground=TEXT_MUTED)
    style.configure("Cardinal.PanelMuted.TLabel", background=SURFACE, foreground=TEXT_MUTED)
    style.configure(
        "Cardinal.Title.TLabel",
        background=BG,
        foreground=TEXT,
        font=(font_family, title_size, "bold"),
    )
    style.configure(
        "Cardinal.Kicker.TLabel",
        background=BG,
        foreground=CRIMSON_SOFT,
        font=(font_family, kicker_size, "bold"),
    )
    style.configure(
        "Cardinal.Status.TLabel",
        background=SURFACE_WARM,
        foreground=AMBER,
        font=(font_family, status_size, "bold"),
        padding=(12, 7),
    )
    style.configure(
        "Cardinal.TButton",
        background=SURFACE_DEEP,
        foreground=TEXT_SECONDARY,
        bordercolor=CRIMSON_DIM,
        lightcolor=CRIMSON_DIM,
        darkcolor=CRIMSON_DIM,
        padding=(11, 7),
        relief="flat",
    )
    style.map(
        "Cardinal.TButton",
        background=[("active", SURFACE_WARM), ("pressed", CRIMSON_BORDER)],
        foreground=[("active", TEXT), ("disabled", TEXT_MUTED)],
        bordercolor=[("active", CRIMSON), ("focus", CRIMSON_SOFT)],
    )
    style.configure(
        "Cardinal.Primary.TButton",
        background=CRIMSON_BORDER,
        foreground=CRIMSON_SOFT,
        bordercolor=CRIMSON,
        padding=(13, 8),
    )
    style.map(
        "Cardinal.Primary.TButton",
        background=[("active", CRIMSON_DIM), ("pressed", CRIMSON)],
        foreground=[("active", TEXT)],
    )
    style.configure(
        "Cardinal.TNotebook",
        background=BG,
        bordercolor=CRIMSON_BORDER,
        lightcolor=CRIMSON_BORDER,
        darkcolor=CRIMSON_BORDER,
        tabmargins=(0, 7, 0, 0),
    )
    style.configure(
        "Cardinal.TNotebook.Tab",
        background=SURFACE_DEEP,
        foreground=TEXT_MUTED,
        bordercolor=CRIMSON_BORDER,
        padding=(18, 8),
    )
    style.map(
        "Cardinal.TNotebook.Tab",
        background=[("selected", SURFACE_WARM), ("active", SURFACE)],
        foreground=[("selected", CRIMSON_SOFT), ("active", TEXT)],
        bordercolor=[("selected", CRIMSON_DIM)],
    )
    style.configure(
        "Cardinal.TEntry",
        fieldbackground=SURFACE_DEEP,
        foreground=TEXT,
        insertcolor=CRIMSON_SOFT,
        bordercolor=CRIMSON_DIM,
        lightcolor=CRIMSON_DIM,
        darkcolor=CRIMSON_DIM,
        padding=7,
    )
    style.map("Cardinal.TEntry", bordercolor=[("focus", CRIMSON_SOFT)])
    style.configure(
        "Cardinal.Vertical.TScrollbar",
        background=CRIMSON_DIM,
        troughcolor=SURFACE_DEEP,
        bordercolor=SURFACE_DEEP,
        arrowcolor=TEXT_MUTED,
    )
    return style

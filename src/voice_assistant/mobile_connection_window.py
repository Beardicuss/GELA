from __future__ import annotations

import json
import sys
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser

from .config import PROJECT_ROOT
from .mobile_bridge import BRIDGE_STATUS_PATH, REGENERATE_REQUEST_PATH
from .private_network import TAILSCALE_DOWNLOAD_URL, enable_private_network_access
from .screen_sharing import grant_screen_sharing, revoke_screen_sharing


class MobileConnectionWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.status = tk.StringVar(value="მობილური ხიდის მდგომარეობა მოწმდება…")
        self.address = tk.StringVar(value="—")
        self.remote_address = tk.StringVar(value="—")
        self.remote_status = tk.StringVar(value="Tailscale-ის მდგომარეობა მოწმდება…")
        self.screen_status = tk.StringVar(value="ეკრანის გაზიარების მდგომარეობა მოწმდება…")
        self.code = tk.StringVar(value="— — — — — —")
        self.expiry = tk.StringVar(value="")

        root.title("Gela — მობილური კავშირი")
        root.geometry("630x690")
        root.minsize(560, 650)
        icon_path = PROJECT_ROOT / "assets" / "icons" / "gela_tray.png"
        if icon_path.is_file():
            self.icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, self.icon_image)
        self._build()
        self._refresh()

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=22)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="მობილური კავშირი", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="დააკავშირეთ ადგილობრივი Wi-Fi-დან ან დაშიფრული კერძო ქსელიდან.",
            foreground="#666666",
        ).pack(anchor="w", pady=(4, 20))

        status_frame = ttk.LabelFrame(outer, text=" ხიდის მდგომარეობა ", padding=14)
        status_frame.pack(fill="x")
        ttk.Label(status_frame, textvariable=self.status, font=("Segoe UI", 11, "bold")).pack(anchor="w")

        details = ttk.Frame(outer)
        details.pack(fill="x", pady=(18, 0))
        ttk.Label(details, text="ადგილობრივი PC მისამართი", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        address_row = ttk.Frame(details)
        address_row.pack(fill="x", pady=(5, 15))
        ttk.Entry(address_row, textvariable=self.address, state="readonly", font=("Consolas", 13)).pack(side="left", fill="x", expand=True)
        ttk.Button(address_row, text="კოპირება", command=lambda: self._copy(self.address.get())).pack(side="left", padx=(8, 0))

        ttk.Label(details, text="დაშიფრული დისტანციური მისამართი", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        remote_row = ttk.Frame(details)
        remote_row.pack(fill="x", pady=(5, 4))
        ttk.Entry(remote_row, textvariable=self.remote_address, state="readonly", font=("Consolas", 11)).pack(side="left", fill="x", expand=True)
        ttk.Button(remote_row, text="კოპირება", command=lambda: self._copy(self.remote_address.get())).pack(side="left", padx=(8, 0))
        ttk.Label(details, textvariable=self.remote_status, foreground="#777777", wraplength=560).pack(anchor="w", pady=(0, 10))
        self.remote_button = ttk.Button(details, text="დისტანციური კავშირის გამართვა", command=self._configure_remote)
        self.remote_button.pack(anchor="w", pady=(0, 16))

        ttk.Separator(details).pack(fill="x", pady=(0, 14))
        ttk.Label(details, text="PC ეკრანის უსაფრთხო ნახვა", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(details, textvariable=self.screen_status, foreground="#777777", wraplength=560).pack(anchor="w", pady=(4, 7))
        self.screen_button = ttk.Button(details, text="ეკრანის ნახვის დაშვება 15 წუთით", command=self._toggle_screen_sharing)
        self.screen_button.pack(anchor="w", pady=(0, 16))

        ttk.Label(details, text="ერთჯერადი დაკავშირების კოდი", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        code_row = ttk.Frame(details)
        code_row.pack(fill="x", pady=(5, 4))
        ttk.Label(code_row, textvariable=self.code, font=("Consolas", 25, "bold"), foreground="#c8392b").pack(side="left")
        ttk.Button(code_row, text="კოდის კოპირება", command=lambda: self._copy(self.code.get().replace(" ", ""))).pack(side="right")
        ttk.Label(details, textvariable=self.expiry, foreground="#777777").pack(anchor="w")

        controls = ttk.Frame(outer)
        controls.pack(fill="x", side="bottom", pady=(20, 0))
        ttk.Button(controls, text="ახალი კოდის შექმნა", command=self._regenerate).pack(side="left")
        ttk.Button(controls, text="დახურვა", command=self.root.destroy).pack(side="right")

    def _copy(self, value: str) -> None:
        if not value or value == "—":
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(value)

    def _regenerate(self) -> None:
        REGENERATE_REQUEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        REGENERATE_REQUEST_PATH.touch()
        self.status.set("ახალი კოდი იქმნება…")

    def _configure_remote(self) -> None:
        private = getattr(self, "private_payload", {})
        if not private.get("installed"):
            webbrowser.open(TAILSCALE_DOWNLOAD_URL)
            self.remote_status.set("დააინსტალირეთ Tailscale, შედით იმავე ანგარიშით PC-სა და Android-ზე, შემდეგ ისევ დააჭირეთ ღილაკს.")
            return
        if not private.get("connected"):
            self.remote_status.set("გახსენით Tailscale Windows tray-დან და შედით ანგარიშში, შემდეგ ისევ სცადეთ.")
            return
        if private.get("remote_base_url"):
            self._copy(str(private["remote_base_url"]))
            self.remote_status.set("კერძო HTTPS მისამართი დაკოპირებულია.")
            return
        self.remote_button.configure(state="disabled")
        self.remote_status.set("Tailscale-ის კერძო HTTPS კავშირი ირთვება…")

        def configure() -> None:
            try:
                status = enable_private_network_access()
                message = f"ჩართულია: {status.remote_base_url}"
            except Exception as exc:
                message = str(exc)
            self.root.after(0, lambda: self._remote_configuration_finished(message))

        threading.Thread(target=configure, name="gela-private-network-setup", daemon=True).start()

    def _remote_configuration_finished(self, message: str) -> None:
        self.remote_button.configure(state="normal")
        self.remote_status.set(message)

    def _toggle_screen_sharing(self) -> None:
        if getattr(self, "screen_payload", {}).get("authorized"):
            revoke_screen_sharing()
            self.screen_status.set("ეკრანის გაზიარება გამორთულია.")
        else:
            status = grant_screen_sharing()
            self.screen_status.set(f"ეკრანის ნახვა დაშვებულია {status.remaining_seconds // 60} წუთით.")

    def _refresh(self) -> None:
        try:
            payload = json.loads(BRIDGE_STATUS_PATH.read_text(encoding="utf-8"))
            running = bool(payload.get("running"))
            error = payload.get("error")
            addresses = payload.get("addresses") or []
            code = str(payload.get("pairing_code", ""))
            remaining = int(payload.get("remaining_seconds", 0))
            used = bool(payload.get("used"))
            private = payload.get("private_network")
            self.private_payload = private if isinstance(private, dict) else {}
            screen = payload.get("screen_sharing")
            self.screen_payload = screen if isinstance(screen, dict) else {}
            self.status.set("● ჩართულია და ელოდება მობილურ კავშირს" if running else f"● გამორთულია{': ' + str(error) if error else ''}")
            self.address.set(str(addresses[0]) if addresses else "მისამართი ვერ მოიძებნა")
            remote = self.private_payload.get("remote_base_url")
            self.remote_address.set(str(remote) if remote else "ჯერ არ არის გამართული")
            if remote:
                self.remote_status.set("● Tailscale Serve ჩართულია — გამოიყენეთ ეს HTTPS მისამართი ნებისმიერი ინტერნეტიდან.")
                self.remote_button.configure(text="დისტანციური მისამართის კოპირება")
            elif self.private_payload.get("connected"):
                self.remote_status.set("Tailscale დაკავშირებულია. ჩართეთ Gela-ს კერძო HTTPS მისამართი.")
                self.remote_button.configure(text="კერძო HTTPS კავშირის ჩართვა")
            elif self.private_payload.get("installed"):
                self.remote_status.set("Tailscale დაყენებულია, მაგრამ ანგარიშში შესვლა ან კავშირი სჭირდება.")
                self.remote_button.configure(text="შესვლის შემდეგ განახლება")
            else:
                self.remote_status.set("სხვადასხვა ინტერნეტიდან კავშირისთვის საჭიროა Tailscale ორივე მოწყობილობაზე.")
                self.remote_button.configure(text="Tailscale-ის ჩამოტვირთვა")
            if self.screen_payload.get("authorized"):
                remaining = int(self.screen_payload.get("remaining_seconds", 0))
                self.screen_status.set(f"● დაშვებულია კიდევ {remaining // 60}:{remaining % 60:02d}. მუშაობს მხოლოდ კერძო HTTPS კავშირით.")
                self.screen_button.configure(text="ეკრანის გაზიარების შეწყვეტა")
            else:
                self.screen_status.set("გამორთულია. დაშვება დროებითია და Gela-ს კერძო HTTPS კავშირს მოითხოვს.")
                self.screen_button.configure(text="ეკრანის ნახვის დაშვება 15 წუთით")
            self.code.set(" ".join(code) if code else "— — — — — —")
            if used:
                self.expiry.set("კოდი უკვე გამოყენებულია. ახალი მოწყობილობისთვის შექმენით ახალი კოდი.")
            elif remaining:
                self.expiry.set(f"კოდი მოქმედებს კიდევ {remaining // 60}:{remaining % 60:02d} წუთი")
            else:
                self.expiry.set("კოდის ვადა გასულია. შექმენით ახალი კოდი.")
        except (OSError, ValueError, json.JSONDecodeError):
            self.status.set("მობილური ხიდის ინფორმაცია ჯერ მიუწვდომელია")
        self.root.after(1000, self._refresh)


def main() -> int:
    root = tk.Tk()
    MobileConnectionWindow(root)
    if "--smoke" in sys.argv:
        root.update_idletasks()
        root.destroy()
        return 0
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

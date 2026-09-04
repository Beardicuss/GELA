from __future__ import annotations

import os
import json
from pathlib import Path
import threading
import subprocess
import sys
import webbrowser

from PIL import Image, ImageDraw, ImageFont
import pystray

from . import __version__
from .catalog import CATALOG_PATH
from .catalog_monitor import CatalogMonitor
from .command_activity import CommandActivityStore
from .config import DEFAULT_CONFIG_PATH, PROJECT_ROOT, USER_DATA_ROOT, load_settings
from .mobile_bridge import MOBILE_TRANSFER_ROOT, MobileBridgeService, ensure_transfer_directories
from .mcu_face import McuFaceBridge
from .mcu_terminal import McuTerminalService
from .pc_health import PcHealthMonitor
from .actions import SystemAction, execute_action
from .responses import VoiceResponses
from .single_instance import SingleInstanceLock
from .startup import install_startup, startup_shortcut, uninstall_startup
from .storage import atomic_write_text
from .worker import LOG_PATH, WorkerControls, run_worker


STATUS_LABELS = {
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
    "calibrating": "გამაღვიძებელი სიტყვის კალიბრაცია",
    "recognition_testing": "ამოცნობის ტესტირება",
    "recognizing_mobile": "მობილურის ხმის ამოცნობა",
    "error": "მიკროფონის ან პროცესის შეცდომა",
    "stopped": "გაჩერებულია",
}
ICON_PATH = PROJECT_ROOT / "assets" / "icons" / "gela_tray.png"
DEVELOPER_URL = "https://softcurse-website.pages.dev/"


def create_icon_image(status: str = "starting") -> Image.Image:
    colors = {
        "sleeping": "#2E7D32",
        "listening_command": "#1565C0",
        "paused": "#757575",
        "error": "#C62828",
    }
    if ICON_PATH.is_file():
        with Image.open(ICON_PATH) as source:
            image = source.convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
    else:
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((4, 4, 60, 60), fill="#5E35B1")
        font = ImageFont.load_default(size=34)
        box = draw.textbbox((0, 0), "G", font=font)
        x = (64 - (box[2] - box[0])) / 2
        y = (64 - (box[3] - box[1])) / 2 - 2
        draw.text((x, y), "G", fill="white", font=font)
    draw = ImageDraw.Draw(image)
    draw.ellipse((44, 44, 62, 62), fill="white")
    draw.ellipse((47, 47, 59, 59), fill=colors.get(status, "#5E35B1"))
    return image


class TrayApplication:
    def __init__(self) -> None:
        self.controls = WorkerControls(self._status_changed)
        self.mcu_face = McuFaceBridge()
        self.pc_health = PcHealthMonitor()
        self.command_activity = CommandActivityStore()
        self.controls.add_status_callback(self.mcu_face.on_status)
        self.controls.add_response_callback(
            lambda event, active: self.mcu_face.on_response(event, active, self.controls.status)
        )
        settings = load_settings()
        catalog_settings = settings.catalog
        self.local_qa_enabled = settings.question_answering.enabled
        self.weather_enabled = settings.online_services.weather_enabled
        self.wikipedia_enabled = settings.online_services.wikipedia_enabled
        self.catalog_interval_seconds = catalog_settings.interval_seconds
        self.catalog_monitor = CatalogMonitor(
            self.controls.stop_event,
            self.controls.reload_event,
            interval_seconds=catalog_settings.interval_seconds,
            enabled=catalog_settings.auto_refresh,
            refresh_on_start=catalog_settings.refresh_on_start,
            callback=self._automatic_catalog_result,
        )
        self.worker_thread: threading.Thread | None = None
        self.catalog_thread: threading.Thread | None = None
        self.calibration_process: subprocess.Popen | None = None
        self.recognition_test_process: subprocess.Popen | None = None
        self.profile_manager_process: subprocess.Popen | None = None
        self.recovery_process: subprocess.Popen | None = None
        self.mobile_window_process: subprocess.Popen | None = None
        self.mobile_bridge = MobileBridgeService(
            audio_recognizer=self.controls.transcribe_remote_audio,
            command_observer=lambda result: self.command_activity.record("MOBILE", result),
        )
        self.mcu_terminal = McuTerminalService(
            audio_recognizer=self.controls.transcribe_remote_audio,
            status_supplier=self._mcu_status,
            cancel=self._cancel_from_mcu,
            toggle_mute=lambda: execute_action(SystemAction("Toggle Mute", "volume_mute")),
            command_observer=lambda result: self.command_activity.record("BOARD", result),
        )
        self.icon = pystray.Icon("GelaVoiceAssistant", create_icon_image(), "Gela Voice Assistant")
        self.icon.menu = self._build_menu()

    def _status_text(self, _item=None) -> str:
        return f"მდგომარეობა: {STATUS_LABELS.get(self.controls.status, self.controls.status)}"

    def _pause_text(self, _item=None) -> str:
        return "მოსმენის გაგრძელება" if self.controls.pause_event.is_set() else "მოსმენის შეჩერება"

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(self._status_text, None, enabled=False),
            pystray.MenuItem(self._pause_text, self._toggle_pause, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "აპლიკაციები",
                pystray.Menu(
                    pystray.MenuItem("კატალოგის განახლება", self._refresh_catalog),
                    pystray.MenuItem(
                        "ავტომატური განახლება (1 საათი)",
                        self._toggle_catalog_refresh,
                        checked=lambda item: self.catalog_monitor.enabled,
                    ),
                    pystray.MenuItem("ხმოვანი სახელების მართვა", self._open_alias_manager),
                    pystray.MenuItem("მართვის პროფილები", self._open_profile_manager),
                    pystray.MenuItem("რუტინების მართვა", self._open_routine_manager),
                    pystray.MenuItem("ხმოვანი მზადყოფნის ნახვა", self._open_catalog_window),
                ),
            ),
            pystray.MenuItem(
                "სერვისები და კავშირი",
                pystray.Menu(
                    pystray.MenuItem("მობილური კავშირი", self._open_mobile_connection),
                    pystray.MenuItem("მობილური ფაილების საქაღალდე", self._open_mobile_transfer_folder),
                    pystray.MenuItem(
                        "ლოკალური კითხვებზე პასუხი",
                        self._toggle_local_qa,
                        checked=lambda item: self.local_qa_enabled,
                    ),
                    pystray.MenuItem(
                        "ონლაინ სერვისები",
                        pystray.Menu(
                            pystray.MenuItem("ამინდი", lambda icon, item: self._toggle_online_service(icon, "weather_enabled"), checked=lambda item: self.weather_enabled),
                            pystray.MenuItem("ვიკიპედია", lambda icon, item: self._toggle_online_service(icon, "wikipedia_enabled"), checked=lambda item: self.wikipedia_enabled),
                        ),
                    ),
                ),
            ),
            pystray.MenuItem(
                "ხმა და დიაგნოსტიკა",
                pystray.Menu(
                    pystray.MenuItem("დიაგნოსტიკა", self._open_diagnostics),
                    pystray.MenuItem("გამაღვიძებელი სიტყვის კალიბრაცია", self._open_calibration),
                    pystray.MenuItem("მეტყველების ამოცნობის ტესტი", self._open_recognition_test),
                    pystray.MenuItem(
                        "ხმოვანი პასუხების ტესტი",
                        pystray.Menu(
                            pystray.MenuItem("მზადაა", lambda icon, item: self._test_response("ready")),
                            pystray.MenuItem(
                                "წარმატებით შესრულდა", lambda icon, item: self._test_response("launch_success")
                            ),
                            pystray.MenuItem(
                                "ვერ გავიგე",
                                lambda icon, item: self._test_response("command_not_understood"),
                            ),
                        ),
                    ),
                    pystray.MenuItem("ხმოვანი პასუხის შეწყვეტა", lambda icon, item: VoiceResponses.stop()),
                    pystray.MenuItem("ჟურნალის გახსნა", self._open_logs_window),
                ),
            ),
            pystray.MenuItem(
                "პარამეტრები",
                pystray.Menu(
                    pystray.MenuItem("პარამეტრების გახსნა", self._open_settings_window),
                    pystray.MenuItem("Gela-ს მონაცემთა საქაღალდე", lambda icon, item: self._open_path(USER_DATA_ROOT)),
                    pystray.MenuItem("დაშიფრული სარეზერვო ასლი", self._open_recovery_window),
                    pystray.MenuItem(
                        "Windows-თან ერთად გაშვება",
                        self._toggle_startup,
                        checked=lambda item: startup_shortcut().is_file(),
                    ),
                ),
            ),
            pystray.MenuItem(
                "Gela-ს შესახებ",
                pystray.Menu(
                    pystray.MenuItem(
                        f"Gela {__version__} — Softcurse Systems", None, enabled=False
                    ),
                    pystray.MenuItem(
                        "Softcurse Systems-ის ვებსაიტი",
                        lambda icon, item: webbrowser.open(DEVELOPER_URL),
                    ),
                ),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Gela-ს დახურვა", self._exit),
        )

    def _status_changed(self, status: str) -> None:
        self.icon.title = f"Gela — {STATUS_LABELS.get(status, status)}"
        self.icon.icon = create_icon_image(status)
        self.icon.update_menu()

    def _mcu_status(self) -> dict[str, object]:
        return {
            "gelaStatus": self.controls.status,
            "faceState": self.mcu_face.desired_state,
            "paused": self.controls.pause_event.is_set(),
            "mobileConnected": self.mobile_bridge.devices.any_recently_seen(),
            "health": self.pc_health.snapshot(),
            "activity": self.command_activity.snapshot(self.controls.status),
        }

    def _cancel_from_mcu(self) -> None:
        VoiceResponses.stop()
        self.controls.request_cancel()

    def _setup(self, icon: pystray.Icon) -> None:
        icon.visible = True
        self.mcu_face.start()
        self.worker_thread = threading.Thread(
            target=run_worker,
            args=(self.controls,),
            name="gela-voice-worker",
            daemon=True,
        )
        self.worker_thread.start()
        self.catalog_thread = threading.Thread(
            target=self.catalog_monitor.run,
            name="gela-catalog-monitor",
            daemon=True,
        )
        self.catalog_thread.start()
        if not self.mobile_bridge.start():
            icon.notify(
                f"მობილური ხიდი ვერ ჩაირთო: {self.mobile_bridge.error}",
                "Gela",
            )
        if not self.mcu_terminal.start():
            icon.notify(f"MCU Wi-Fi bridge could not start: {self.mcu_terminal.error}", "Gela")

    def _toggle_pause(self, icon, item) -> None:
        VoiceResponses.stop()
        if self.controls.pause_event.is_set():
            self.controls.pause_event.clear()
        else:
            self.controls.pause_event.set()
        icon.update_menu()

    def _refresh_catalog(self, icon, item) -> None:
        try:
            count, changed = self.catalog_monitor.refresh(invoke_callback=False)
            result = "კატალოგი განახლდა" if changed else "ცვლილებები ვერ მოიძებნა"
            icon.notify(f"კატალოგის სკანირება დასრულდა: {count} ჩანაწერი; {result}", "Gela")
        except Exception as exc:
            icon.notify(f"კატალოგის განახლება ვერ მოხერხდა: {exc}", "Gela")

    def _automatic_catalog_result(self, count: int, changed: bool) -> None:
        if changed:
            self.icon.notify(f"აპლიკაციების კატალოგი განახლდა: {count} ჩანაწერი", "Gela")

    def _toggle_catalog_refresh(self, icon, item) -> None:
        try:
            self.catalog_monitor.set_enabled(not self.catalog_monitor.enabled)
            icon.update_menu()
        except Exception as exc:
            icon.notify(f"ავტომატური განახლების პარამეტრი ვერ შეინახა: {exc}", "Gela")

    def _toggle_local_qa(self, icon, item) -> None:
        try:
            raw = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
            enabled = not self.local_qa_enabled
            raw["question_answering"]["enabled"] = enabled
            atomic_write_text(
                DEFAULT_CONFIG_PATH,
                json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
            )
            self.local_qa_enabled = enabled
            self.controls.reload_event.set()
            icon.update_menu()
            message = (
                "ლოკალური კითხვები ჩაირთო. ლოკალური მოდელის სერვისი გაშვებული უნდა იყოს."
                if enabled
                else "ლოკალური კითხვები გამოირთო."
            )
            icon.notify(message, "Gela")
        except Exception as exc:
            icon.notify(f"ლოკალური კითხვების პარამეტრი ვერ შეიცვალა: {exc}", "Gela")

    def _toggle_online_service(self, icon, setting: str) -> None:
        try:
            raw = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
            attribute = "weather_enabled" if setting == "weather_enabled" else "wikipedia_enabled"
            enabled = not bool(getattr(self, attribute))
            raw["online_services"][setting] = enabled
            atomic_write_text(DEFAULT_CONFIG_PATH, json.dumps(raw, ensure_ascii=False, indent=2) + "\n")
            setattr(self, attribute, enabled)
            self.controls.reload_event.set()
            icon.update_menu()
            service = "ამინდი" if setting == "weather_enabled" else "ვიკიპედია"
            icon.notify(f"{service} {'ჩაირთო' if enabled else 'გამოირთო'}", "Gela")
        except Exception as exc:
            icon.notify(f"ონლაინ სერვისის პარამეტრი ვერ შეიცვალა: {exc}", "Gela")

    def _test_response(self, event: str) -> None:
        was_paused = self.controls.pause_event.is_set()
        self.controls.pause_event.set()
        try:
            VoiceResponses().play(event)
        finally:
            if not was_paused:
                self.controls.pause_event.clear()

    @staticmethod
    def _open_alias_manager(icon, item) -> None:
        if getattr(sys, "frozen", False):
            subprocess.Popen([sys.executable, "--alias-manager"], close_fds=True)
        else:
            subprocess.Popen([sys.executable, "-m", "voice_assistant.alias_manager"], close_fds=True)

    def _open_profile_manager(self, icon, item) -> None:
        if self.profile_manager_process is not None and self.profile_manager_process.poll() is None:
            icon.notify("აპლიკაციების პროფილების ფანჯარა უკვე გახსნილია", "Gela")
            return
        command = (
            [sys.executable, "--profile-manager"]
            if getattr(sys, "frozen", False)
            else [sys.executable, "-m", "voice_assistant.profile_manager"]
        )

        def launch_and_reload() -> None:
            try:
                self.profile_manager_process = subprocess.Popen(command, close_fds=True)
                self.profile_manager_process.wait()
            except Exception as exc:
                icon.notify(f"პროფილების ფანჯარა ვერ გაიხსნა: {exc}", "Gela")
            finally:
                self.controls.reload_event.set()

        threading.Thread(
            target=launch_and_reload,
            name="gela-profile-manager",
            daemon=True,
        ).start()

    @staticmethod
    def _open_diagnostics(icon, item) -> None:
        if getattr(sys, "frozen", False):
            subprocess.Popen([sys.executable, "--diagnostics"], close_fds=True)
        else:
            subprocess.Popen([sys.executable, "-m", "voice_assistant.diagnostics"], close_fds=True)

    @staticmethod
    def _open_routine_manager(icon, item) -> None:
        if getattr(sys, "frozen", False):
            subprocess.Popen([sys.executable, "--routine-manager"], close_fds=True)
        else:
            subprocess.Popen([sys.executable, "-m", "voice_assistant.routine_manager"], close_fds=True)

    @staticmethod
    def _open_logs_window(icon, item) -> None:
        command = (
            [sys.executable, "--logs-window"]
            if getattr(sys, "frozen", False)
            else [sys.executable, "-m", "voice_assistant.logs_window"]
        )
        subprocess.Popen(command, close_fds=True)

    def _open_mobile_connection(self, icon, item) -> None:
        if self.mobile_window_process is not None and self.mobile_window_process.poll() is None:
            icon.notify("მობილური კავშირის ფანჯარა უკვე გახსნილია", "Gela")
            return
        command = (
            [sys.executable, "--mobile-connection"]
            if getattr(sys, "frozen", False)
            else [sys.executable, "-m", "voice_assistant.mobile_connection_window"]
        )
        try:
            self.mobile_window_process = subprocess.Popen(command, close_fds=True)
        except Exception as exc:
            icon.notify(f"მობილური კავშირის ფანჯარა ვერ გაიხსნა: {exc}", "Gela")

    @staticmethod
    def _open_catalog_window(icon, item) -> None:
        command = (
            [sys.executable, "--catalog-window"]
            if getattr(sys, "frozen", False)
            else [sys.executable, "-m", "voice_assistant.catalog_window"]
        )
        subprocess.Popen(command, close_fds=True)

    def _open_settings_window(self, icon, item) -> None:
        command = (
            [sys.executable, "--settings-window"]
            if getattr(sys, "frozen", False)
            else [sys.executable, "-m", "voice_assistant.settings_window"]
        )

        def launch_and_reload() -> None:
            process = subprocess.Popen(command, close_fds=True)
            process.wait()
            self.controls.reload_event.set()

        threading.Thread(target=launch_and_reload, name="gela-settings-window", daemon=True).start()

    def _open_calibration(self, icon, item) -> None:
        if self.calibration_process is not None and self.calibration_process.poll() is None:
            icon.notify("გამაღვიძებელი სიტყვის კალიბრაცია უკვე გახსნილია", "Gela")
            return
        if self.recognition_test_process is not None and self.recognition_test_process.poll() is None:
            icon.notify("ჯერ დახურეთ მეტყველების ამოცნობის ტესტი", "Gela")
            return
        self.controls.request_audio_release("calibrating")

        def launch_when_released() -> None:
            deadline = __import__("time").monotonic() + 5.0
            while self.controls.status != "calibrating" and __import__("time").monotonic() < deadline:
                if self.controls.stop_event.wait(0.05):
                    return
            if self.controls.status != "calibrating":
                self.controls.release_audio_event.clear()
                icon.notify("კალიბრაციისთვის მიკროფონის გათავისუფლება ვერ მოხერხდა", "Gela")
                return
            try:
                command = (
                    [sys.executable, "--calibration"]
                    if getattr(sys, "frozen", False)
                    else [sys.executable, "-m", "voice_assistant.calibration"]
                )
                self.calibration_process = subprocess.Popen(command, close_fds=True)
                self.calibration_process.wait()
            except Exception as exc:
                icon.notify(f"კალიბრაცია ვერ გაიხსნა: {exc}", "Gela")
            finally:
                self.controls.release_audio_event.clear()
                self.controls.reload_event.set()

        threading.Thread(target=launch_when_released, name="gela-calibration-launcher", daemon=True).start()

    def _open_recognition_test(self, icon, item) -> None:
        if self.recognition_test_process is not None and self.recognition_test_process.poll() is None:
            icon.notify("მეტყველების ამოცნობის ტესტი უკვე გახსნილია", "Gela")
            return
        if self.calibration_process is not None and self.calibration_process.poll() is None:
            icon.notify("ჯერ დახურეთ გამაღვიძებელი სიტყვის კალიბრაცია", "Gela")
            return
        self.controls.request_audio_release("recognition_testing")

        def launch_when_released() -> None:
            deadline = __import__("time").monotonic() + 5.0
            while (
                self.controls.status != "recognition_testing"
                and __import__("time").monotonic() < deadline
            ):
                if self.controls.stop_event.wait(0.05):
                    return
            if self.controls.status != "recognition_testing":
                self.controls.release_audio_event.clear()
                icon.notify("ტესტისთვის მიკროფონის გათავისუფლება ვერ მოხერხდა", "Gela")
                return
            try:
                command = (
                    [sys.executable, "--recognition-test"]
                    if getattr(sys, "frozen", False)
                    else [sys.executable, "-m", "voice_assistant.recognition_test_window"]
                )
                self.recognition_test_process = subprocess.Popen(command, close_fds=True)
                self.recognition_test_process.wait()
            except Exception as exc:
                icon.notify(f"ამოცნობის ტესტი ვერ გაიხსნა: {exc}", "Gela")
            finally:
                self.controls.release_audio_event.clear()
                self.controls.reload_event.set()

        threading.Thread(
            target=launch_when_released,
            name="gela-recognition-test-launcher",
            daemon=True,
        ).start()

    @staticmethod
    def _open_path(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() and path == LOG_PATH:
            path.touch()
        os.startfile(path)  # type: ignore[attr-defined]

    def _open_mobile_transfer_folder(self, _icon=None, _item=None) -> None:
        ensure_transfer_directories()
        self._open_path(MOBILE_TRANSFER_ROOT)

    def _open_recovery_window(self, icon, item) -> None:
        if self.recovery_process is not None and self.recovery_process.poll() is None:
            icon.notify("Gela Recovery უკვე გახსნილია", "Gela")
            return
        command = (
            [sys.executable, "--recovery"]
            if getattr(sys, "frozen", False)
            else [sys.executable, "-m", "voice_assistant.recovery_window"]
        )
        self.recovery_process = subprocess.Popen(command, close_fds=True)

    @staticmethod
    def _open_text_file(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.touch()
        subprocess.Popen(["notepad.exe", str(path)], close_fds=True)

    def _toggle_startup(self, icon, item) -> None:
        if startup_shortcut().is_file():
            uninstall_startup()
        else:
            install_startup()
        icon.update_menu()

    def _exit(self, icon, item) -> None:
        VoiceResponses.stop()
        self.controls.stop_event.set()
        self.mcu_terminal.stop()
        self.mobile_bridge.stop()
        self.mcu_face.stop()
        icon.stop()

    def run(self) -> None:
        self.icon.run(setup=self._setup)
        self.controls.stop_event.set()
        self.mcu_terminal.stop()
        self.mobile_bridge.stop()
        self.mcu_face.stop()
        if self.worker_thread is not None:
            self.worker_thread.join(timeout=3)
        if self.catalog_thread is not None:
            self.catalog_thread.join(timeout=3)


def main() -> int:
    if "--sleep-helper" in sys.argv:
        from .sleep_helper import main as sleep_helper_main

        return sleep_helper_main()
    if "--mobile-connection" in sys.argv:
        from .mobile_connection_window import main as mobile_connection_main

        return mobile_connection_main()
    if "--recovery" in sys.argv:
        from .recovery_window import main as recovery_main

        return recovery_main()
    if "--catalog-window" in sys.argv:
        from .catalog_window import main as catalog_window_main

        return catalog_window_main()
    if "--recognition-test" in sys.argv:
        from .recognition_test_window import main as recognition_test_main

        return recognition_test_main()
    if "--profile-manager" in sys.argv:
        from .profile_manager import main as profile_manager_main

        return profile_manager_main()
    if "--settings-window" in sys.argv:
        from .settings_window import main as settings_window_main

        return settings_window_main()
    if "--logs-window" in sys.argv:
        from .logs_window import main as logs_window_main

        return logs_window_main()
    if "--answer-window" in sys.argv:
        from .answer_window import main as answer_window_main

        index = sys.argv.index("--answer-window")
        path = Path(sys.argv[index + 1]) if len(sys.argv) > index + 1 else None
        return answer_window_main(path)
    if "--alias-manager" in sys.argv:
        from .alias_manager import main as alias_manager_main

        return alias_manager_main()
    if "--diagnostics" in sys.argv:
        from .diagnostics import main as diagnostics_main

        return diagnostics_main()
    if "--calibration" in sys.argv:
        from .calibration import main as calibration_main

        return calibration_main()
    if "--routine-manager" in sys.argv:
        from .routine_manager import main as routine_manager_main

        return routine_manager_main()
    instance_lock = SingleInstanceLock()
    if not instance_lock.acquire():
        return 0
    try:
        TrayApplication().run()
    finally:
        instance_lock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

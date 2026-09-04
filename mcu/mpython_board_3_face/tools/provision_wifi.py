"""Provision board Wi-Fi without placing its password in shell history."""
from getpass import getpass
import argparse, json, re, subprocess, sys
from pathlib import Path
import serial.tools.list_ports

BOARD_VID=0x303A; BOARD_PID=0x1001
TOKEN_PATH=Path.home()/"AppData"/"Local"/"Gela"/"mcu"/"board_token.txt"
def board_port():
    ports=[p.device for p in serial.tools.list_ports.comports() if p.vid==BOARD_VID and p.pid==BOARD_PID]
    if not ports:raise SystemExit("Board not found. Connect it directly by USB and close Gela first.")
    return sorted(ports)[0]
def current_ssid():
    output=subprocess.run(["netsh","wlan","show","interfaces"],capture_output=True,text=True).stdout
    match=re.search(r"^\s*SSID\s*:\s*(.+)$",output,re.MULTILINE)
    return match.group(1).strip() if match else ""
def provision(ssid,password):
    if not ssid or not password:raise SystemExit("Wi-Fi name and password are required.")
    config=json.dumps({"ssid":ssid,"password":password,"host":"","token":TOKEN_PATH.read_text(encoding="ascii").strip()},ensure_ascii=True)
    temporary=Path(__file__).resolve().parent.parent/"build"/"gela_config.json"; temporary.write_text(config,encoding="ascii")
    mpremote=Path(sys.executable).with_name("mpremote.exe")
    try:subprocess.run([str(mpremote),"connect",board_port(),"fs","cp",str(temporary),":gela_config.json"],check=True)
    finally:temporary.unlink(missing_ok=True)
    print("Board Wi-Fi configured. Press Reset on the board.")
def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--gui",action="store_true"); args=parser.parse_args(); default=current_ssid()
    if args.gui:
        import tkinter as tk
        from tkinter import messagebox, simpledialog
        root=tk.Tk(); root.withdraw(); ssid=simpledialog.askstring("Gela Board Wi-Fi","Wi-Fi name:",initialvalue=default,parent=root)
        if ssid is None:return
        password=simpledialog.askstring("Gela Board Wi-Fi","Wi-Fi password:",show="*",parent=root)
        if password is None:return
        try:provision(ssid.strip(),password)
        except Exception as exc:messagebox.showerror("Gela Board Wi-Fi",str(exc),parent=root); raise
        else:messagebox.showinfo("Gela Board Wi-Fi","Configured. The board will restart and connect automatically.",parent=root)
        finally:root.destroy()
    else:
        ssid=input("Wi-Fi name [%s]: "%default).strip() or default; provision(ssid,getpass("Wi-Fi password (hidden): "))
if __name__=="__main__":main()

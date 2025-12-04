#!/usr/bin/env python3
import socket
import threading
from collections import deque
from pathlib import Path
import tkinter as tk

import sounddevice as sd

LISTEN_IP = "0.0.0.0"
LISTEN_PORT = 5004

SAMPLE_RATE = 48000
CHANNELS = 2
CHUNK = 1024
BYTES_PER_SAMPLE = 2
PACKET_SIZE = CHUNK * CHANNELS * BYTES_PER_SAMPLE

CONFIG_DIR = Path.home() / ".vox"
CONFIG_FILE = CONFIG_DIR / "config.txt"
CONFIG_LISTEN_KEY = "listen_ip"


def load_config():
    try:
        data = {}
        if CONFIG_FILE.exists():
            for line in CONFIG_FILE.read_text().splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    data[key.strip()] = value.strip()
        return data
    except Exception:
        return {}


def save_config_entry(key, value):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config = load_config()
        config[key] = value
        CONFIG_FILE.write_text("\n".join(f"{k}={v}" for k, v in config.items()))
    except Exception as exc:
        print(f"Could not save config: {exc}", flush=True)


def build_gui(default_ip):
    root = tk.Tk()
    root.title("Vox Listener")

    status_var = tk.StringVar(value="Idle")
    button_var = tk.StringVar(value="Start Listening")
    ip_var = tk.StringVar(value=default_ip)

    status_label = tk.Label(root, textvariable=status_var, font=("Helvetica", 12))
    status_label.pack(padx=12, pady=8)

    ip_label = tk.Label(root, text="Listen IP")
    ip_label.pack(padx=12, pady=(8, 2))
    ip_entry = tk.Entry(root, textvariable=ip_var, width=22)
    ip_entry.pack(padx=12, pady=(0, 6))

    start_button = tk.Button(root, textvariable=button_var, width=18)
    start_button.pack(padx=12, pady=4)

    return root, status_var, button_var, ip_var, start_button


def main():
    running = threading.Event()
    closing = threading.Event()

    packets_lock = threading.Lock()
    packets_this_second = {"count": 0}
    last_ten_seconds = deque(maxlen=10)
    console_lock = threading.Lock()

    listen_thread = None
    console_thread = None

    config = load_config()
    default_ip = config.get(CONFIG_LISTEN_KEY, LISTEN_IP)

    root, status_var, button_var, ip_var, start_button = build_gui(default_ip)

    def safe_set(var, value):
        try:
            var.set(value)
        except tk.TclError:
            pass

    def update_status():
        if closing.is_set():
            return
        with packets_lock:
            last_ten_seconds.append(packets_this_second["count"])
            packets_this_second["count"] = 0
        avg = (sum(last_ten_seconds) / len(last_ten_seconds)) if last_ten_seconds else 0.0
        safe_set(status_var, f"Average: {avg:.1f} packets/s (last 10s)" if running.is_set() else "Idle")
        root.after(1000, update_status)

    def listen_audio(listen_ip):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((listen_ip, LISTEN_PORT))
            sock.settimeout(1.0)
            with sd.RawOutputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK,
            ) as stream:
                while running.is_set():
                    try:
                        data, _ = sock.recvfrom(PACKET_SIZE)
                    except socket.timeout:
                        continue
                    if len(data) != PACKET_SIZE:
                        continue
                    stream.write(data)
                    with packets_lock:
                        packets_this_second["count"] += 1
        except Exception as exc:
            safe_set(status_var, f"Error: {exc}")
        finally:
            sock.close()
            running.clear()
            safe_set(button_var, "Start Listening")

    def start():
        nonlocal listen_thread
        if running.is_set():
            running.clear()
            safe_set(button_var, "Start Listening")
            return
        listen_ip = ip_var.get().strip()
        if not listen_ip:
            safe_set(status_var, "Enter the listen IP before starting")
            return
        save_config_entry(CONFIG_LISTEN_KEY, listen_ip)
        running.set()
        with packets_lock:
            packets_this_second["count"] = 0
            last_ten_seconds.clear()
        safe_set(button_var, "Stop")
        listen_thread = threading.Thread(target=listen_audio, args=(listen_ip,), daemon=True)
        listen_thread.start()
        def console_report():
            while running.is_set() and not closing.is_set():
                time.sleep(1)
                with packets_lock:
                    count = packets_this_second["count"]
                with console_lock:
                    pass
                with console_lock:
                    print(f"[listener] packets last second: {count}", flush=True)
        console_thread = threading.Thread(target=console_report, daemon=True)
        console_thread.start()

    def on_close():
        closing.set()
        running.clear()
        if listen_thread and listen_thread.is_alive():
            listen_thread.join(timeout=2)
        if console_thread and console_thread.is_alive():
            console_thread.join(timeout=2)
        root.destroy()

    start_button.configure(command=start)
    root.protocol("WM_DELETE_WINDOW", on_close)
    update_status()
    root.mainloop()


if __name__ == "__main__":
    main()

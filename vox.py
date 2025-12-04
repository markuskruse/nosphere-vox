#!/usr/bin/env python3
import socket
import threading
from collections import deque
from pathlib import Path
import tkinter as tk

import sounddevice as sd

# Defaults used when no config is present.
DEFAULT_TARGET_IP = "192.168.68.100"
DEFAULT_LISTEN_IP = "0.0.0.0"   # listen on all interfaces by default
PORT = 5004

SAMPLE_RATE = 48000
CHANNELS = 2
CHUNK = 1024
BYTES_PER_SAMPLE = 2  # int16
PACKET_SIZE = CHUNK * CHANNELS * BYTES_PER_SAMPLE

CONFIG_DIR = Path.home() / ".vox"
CONFIG_FILE = CONFIG_DIR / "config.txt"
CONFIG_TARGET_KEY = "target_ip"
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


def build_gui(default_target_ip, default_listen_ip):
    root = tk.Tk()
    root.title("Vox")

    status_var = tk.StringVar(value="Idle")
    send_button_var = tk.StringVar(value="Start Sending")
    listen_button_var = tk.StringVar(value="Start Listening")
    target_ip_var = tk.StringVar(value=default_target_ip)
    listen_ip_var = tk.StringVar(value=default_listen_ip)

    status_label = tk.Label(root, textvariable=status_var, font=("Helvetica", 12))
    status_label.pack(padx=12, pady=8)

    target_label = tk.Label(root, text="Target IP")
    target_label.pack(padx=12, pady=(6, 2))
    target_entry = tk.Entry(root, textvariable=target_ip_var, width=22)
    target_entry.pack(padx=12, pady=(0, 6))

    listen_label = tk.Label(root, text="Listen IP")
    listen_label.pack(padx=12, pady=(6, 2))
    listen_entry = tk.Entry(root, textvariable=listen_ip_var, width=22)
    listen_entry.pack(padx=12, pady=(0, 6))

    send_button = tk.Button(root, textvariable=send_button_var, width=18)
    send_button.pack(padx=12, pady=(6, 4))

    listen_button = tk.Button(root, textvariable=listen_button_var, width=18)
    listen_button.pack(padx=12, pady=(0, 8))

    return (
        root,
        status_var,
        send_button_var,
        listen_button_var,
        target_ip_var,
        listen_ip_var,
        send_button,
        listen_button,
    )


def main():
    send_running = threading.Event()
    listen_running = threading.Event()
    closing = threading.Event()

    send_packets_lock = threading.Lock()
    send_packets_this_second = {"count": 0}
    send_last_ten_seconds = deque(maxlen=10)

    listen_packets_lock = threading.Lock()
    listen_packets_this_second = {"count": 0}
    listen_last_ten_seconds = deque(maxlen=10)

    send_thread = None
    listen_thread = None

    config = load_config()
    default_target_ip = config.get(CONFIG_TARGET_KEY, DEFAULT_TARGET_IP)
    default_listen_ip = config.get(CONFIG_LISTEN_KEY, DEFAULT_LISTEN_IP)

    (
        root,
        status_var,
        send_button_var,
        listen_button_var,
        target_ip_var,
        listen_ip_var,
        send_button,
        listen_button,
    ) = build_gui(default_target_ip, default_listen_ip)

    def safe_set(var, value):
        try:
            var.set(value)
        except tk.TclError:
            pass

    def update_status():
        if closing.is_set():
            return

        with send_packets_lock:
            send_last_ten_seconds.append(send_packets_this_second["count"])
            send_packets_this_second["count"] = 0

        with listen_packets_lock:
            listen_last_ten_seconds.append(listen_packets_this_second["count"])
            listen_packets_this_second["count"] = 0

        if send_running.is_set():
            avg = (sum(send_last_ten_seconds) / len(send_last_ten_seconds)) if send_last_ten_seconds else 0.0
            safe_set(status_var, f"Sending: {avg:.1f} packets/s (last 10s)")
        elif listen_running.is_set():
            avg = (sum(listen_last_ten_seconds) / len(listen_last_ten_seconds)) if listen_last_ten_seconds else 0.0
            safe_set(status_var, f"Listening: {avg:.1f} packets/s (last 10s)")
        else:
            safe_set(status_var, "Idle")

        root.after(1000, update_status)

    def send_audio(target_ip):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK,
            ) as stream:
                while send_running.is_set():
                    frames, overflowed = stream.read(CHUNK)
                    if overflowed:
                        print("Warning: input overflow", flush=True)
                    sock.sendto(frames.tobytes(), (target_ip, PORT))
                    with send_packets_lock:
                        send_packets_this_second["count"] += 1
        except Exception as exc:
            safe_set(status_var, f"Error sending: {exc}")
        finally:
            sock.close()
            send_running.clear()
            safe_set(send_button_var, "Start Sending")

    def listen_audio(listen_ip):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((listen_ip, PORT))
        sock.settimeout(1.0)
        try:
            with sd.RawOutputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK,
            ) as stream:
                while listen_running.is_set():
                    try:
                        data, _ = sock.recvfrom(PACKET_SIZE)
                    except socket.timeout:
                        continue
                    if len(data) != PACKET_SIZE:
                        continue
                    stream.write(data)
                    with listen_packets_lock:
                        listen_packets_this_second["count"] += 1
        except Exception as exc:
            safe_set(status_var, f"Error listening: {exc}")
        finally:
            sock.close()
            listen_running.clear()
            safe_set(listen_button_var, "Start Listening")

    def start_send():
        nonlocal send_thread
        if listen_running.is_set():
            safe_set(status_var, "Stop listening before sending")
            return
        if send_running.is_set():
            send_running.clear()
            safe_set(send_button_var, "Start Sending")
            return
        target_ip = target_ip_var.get().strip()
        if not target_ip:
            safe_set(status_var, "Enter the target IP before starting")
            return
        save_config_entry(CONFIG_TARGET_KEY, target_ip)
        send_running.set()
        with send_packets_lock:
            send_packets_this_second["count"] = 0
            send_last_ten_seconds.clear()
        safe_set(send_button_var, "Stop Sending")
        send_thread = threading.Thread(target=send_audio, args=(target_ip,), daemon=True)
        send_thread.start()

    def start_listen():
        nonlocal listen_thread
        if send_running.is_set():
            safe_set(status_var, "Stop sending before listening")
            return
        if listen_running.is_set():
            listen_running.clear()
            safe_set(listen_button_var, "Start Listening")
            return
        listen_ip = listen_ip_var.get().strip()
        if not listen_ip:
            safe_set(status_var, "Enter the listen IP before starting")
            return
        save_config_entry(CONFIG_LISTEN_KEY, listen_ip)
        listen_running.set()
        with listen_packets_lock:
            listen_packets_this_second["count"] = 0
            listen_last_ten_seconds.clear()
        safe_set(listen_button_var, "Stop Listening")
        listen_thread = threading.Thread(target=listen_audio, args=(listen_ip,), daemon=True)
        listen_thread.start()

    def on_close():
        closing.set()
        send_running.clear()
        listen_running.clear()
        if send_thread and send_thread.is_alive():
            send_thread.join(timeout=2)
        if listen_thread and listen_thread.is_alive():
            listen_thread.join(timeout=2)
        root.destroy()

    send_button.configure(command=start_send)
    listen_button.configure(command=start_listen)
    root.protocol("WM_DELETE_WINDOW", on_close)
    update_status()
    root.mainloop()


if __name__ == "__main__":
    main()

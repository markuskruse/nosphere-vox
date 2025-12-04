#!/usr/bin/env python3
import socket
import threading
from collections import deque
import tkinter as tk

import sounddevice as sd

LISTEN_IP = "0.0.0.0"   # listen on all interfaces
LISTEN_PORT = 5004

SAMPLE_RATE = 48000
CHANNELS = 2
CHUNK = 1024  # must match sender
BYTES_PER_SAMPLE = 2  # int16

PACKET_SIZE = CHUNK * CHANNELS * BYTES_PER_SAMPLE

def build_gui():
    root = tk.Tk()
    root.title("Vox Listener")

    status_var = tk.StringVar(value="Idle")
    button_var = tk.StringVar(value="Start Listening")

    status_label = tk.Label(root, textvariable=status_var, font=("Helvetica", 12))
    status_label.pack(padx=12, pady=8)

    start_button = tk.Button(root, textvariable=button_var, width=18)
    start_button.pack(padx=12, pady=4)

    return root, status_var, button_var, start_button


def main():
    running = threading.Event()
    packets_lock = threading.Lock()
    packets_this_second = {"count": 0}
    last_ten_seconds = deque(maxlen=10)

    root, status_var, button_var, start_button = build_gui()

    def update_status():
        with packets_lock:
            last_ten_seconds.append(packets_this_second["count"])
            packets_this_second["count"] = 0
        avg = (sum(last_ten_seconds) / len(last_ten_seconds)) if last_ten_seconds else 0.0
        status_var.set(f"Average: {avg:.1f} packets/s (last 10s)")
        root.after(1000, update_status)

    def listen_audio():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((LISTEN_IP, LISTEN_PORT))
        sock.settimeout(1.0)
        try:
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
            status_var.set(f"Error: {exc}")
        finally:
            sock.close()
            running.clear()
            button_var.set("Start Listening")

    def start():
        if running.is_set():
            running.clear()
            button_var.set("Start Listening")
            return
        running.set()
        with packets_lock:
            packets_this_second["count"] = 0
            last_ten_seconds.clear()
        button_var.set("Stop")
        thread = threading.Thread(target=listen_audio, daemon=True)
        thread.start()

    def on_close():
        running.clear()
        root.destroy()

    start_button.configure(command=start)
    root.protocol("WM_DELETE_WINDOW", on_close)
    update_status()
    root.mainloop()

if __name__ == "__main__":
    main()

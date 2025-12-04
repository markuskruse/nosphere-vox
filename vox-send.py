#!/usr/bin/env python3
import socket
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 48000
CHANNELS = 2
CHUNK = 1024
BYTES_PER_SAMPLE = 2
PACKET_SIZE = CHUNK * CHANNELS * BYTES_PER_SAMPLE
PORT = 5004

CONFIG_DIR = Path.home() / ".vox"
CONFIG_FILE = CONFIG_DIR / "config.txt"
CONFIG_TARGET_KEY = "target_ip"


def load_config_target():
    try:
        if CONFIG_FILE.exists():
            for line in CONFIG_FILE.read_text().splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    if key.strip() == CONFIG_TARGET_KEY:
                        return value.strip()
    except Exception:
        pass
    return None


def main():
    target_ip = load_config_target()
    if not target_ip:
        print("No target_ip found in ~/.vox/config.txt", file=sys.stderr)
        sys.exit(1)

    device = "pulse"
    try:
        sd.check_input_settings(
            device=device,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
        )
    except Exception as exc:
        print(f"Device check failed for '{device}': {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Headless meter/send: device='{device}', target={target_ip}:{PORT}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK,
            device=device,
        ) as stream:
            levels = []
            last_print = time.time()
            packets = 0
            while True:
                data, overflowed = stream.read(CHUNK)
                if overflowed:
                    print("Warning: input overflow", flush=True)
                if len(data) != PACKET_SIZE:
                    continue
                sock.sendto(data, (target_ip, PORT))
                packets += 1
                samples = np.frombuffer(data, dtype=np.int16).astype(np.int32)
                if samples.size:
                    rms = float(np.sqrt(np.mean(samples * samples))) / 32768.0
                    levels.append(rms)
                now = time.time()
                if now - last_print >= 1.0:
                    if levels:
                        avg = sum(levels) / len(levels)
                        bars = max(1, min(20, int(avg * 20)))
                        print(f"packets: {packets:5d} volume: " + ("*" * bars).ljust(20), flush=True)
                        levels.clear()
                        packets = 0
                    last_print = now
    except KeyboardInterrupt:
        sys.stdout.write("\r" + " " * 40 + "\r")
        sys.stdout.flush()
        print("Stopping.")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        sock.close()


if __name__ == "__main__":
    main()

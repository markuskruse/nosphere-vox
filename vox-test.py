#!/usr/bin/env python3
import argparse
import socket
import sys
import time
from pathlib import Path

import numpy as np

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
    parser = argparse.ArgumentParser(description="Headless test tone sender")
    parser.add_argument("--ip", help="Target IP (overrides config)")
    args = parser.parse_args()

    target_ip = args.ip or load_config_target()
    if not target_ip:
        print("No target_ip found in ~/.vox/config.txt (and none provided)", file=sys.stderr)
        sys.exit(1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    omega = 2 * np.pi * 440.0 / SAMPLE_RATE
    phase = 0.0
    tone_every_chunks = 50   # roughly once per second
    tone_length_chunks = 5   # ~0.1s tone
    chunk_counter = 0

    print(f"Sending test tone bursts to {target_ip}:{PORT}. Ctrl+C to stop.")
    try:
        levels = []
        packets = 0
        last_print = time.time()
        while True:
            use_tone = (chunk_counter % tone_every_chunks) < tone_length_chunks
            if use_tone:
                phase_arr = phase + omega * np.arange(CHUNK)
                samples = 0.25 * np.sin(phase_arr)
                phase = (phase_arr[-1] + omega) % (2 * np.pi)
                frames = (samples[:, None] * np.ones((1, CHANNELS))).astype(np.float32)
                frames = np.clip(frames * 32767, -32768, 32767).astype(np.int16)
            else:
                frames = np.zeros((CHUNK, CHANNELS), dtype=np.int16)

            buf = frames.tobytes()
            sock.sendto(buf, (target_ip, PORT))
            chunk_counter += 1
            packets += 1
            # crude RMS for reporting
            samples_int = np.frombuffer(buf, dtype=np.int16).astype(np.int32)
            if samples_int.size:
                rms = float(np.sqrt(np.mean(samples_int * samples_int))) / 32768.0
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
            time.sleep(CHUNK / SAMPLE_RATE)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        sock.close()


if __name__ == "__main__":
    main()

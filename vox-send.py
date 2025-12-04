#!/usr/bin/env python3
import argparse
import socket
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import subprocess
import os

SAMPLE_RATE = 48000
CHANNELS = 2
CHUNK = 1024
BYTES_PER_SAMPLE = 2
PACKET_SIZE = CHUNK * CHANNELS * BYTES_PER_SAMPLE
PORT = 5004

CONFIG_DIR = Path.home() / ".vox"
CONFIG_FILE = CONFIG_DIR / "config.txt"
CONFIG_TARGET_KEY = "target_ip"
SETUP_SCRIPT = Path(__file__).with_name("setup-vox-meter-sink.sh")
TEARDOWN_SCRIPT = Path(__file__).with_name("teardown-vox-meter-sink.sh")


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
    parser = argparse.ArgumentParser(description="Headless sender")
    parser.add_argument("--ip", help="Target IP (overrides config)")
    parser.add_argument("--port", type=int, default=PORT, help="Target UDP port (default: 5004)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable periodic console logs")
    parser.add_argument("--auto-sink", action="store_true", help="On Linux, ensure vox_meter sink exists (runs setup script if missing) and tear down on exit.")
    args = parser.parse_args()

    target_ip = args.ip or load_config_target()
    if not target_ip:
        print("No target_ip found in ~/.vox/config.txt (and none provided)", file=sys.stderr)
        sys.exit(1)
    port = args.port

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

    print(f"Headless meter/send: device='{device}', target={target_ip}:{port}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ran_setup = False

    def ensure_sink():
        nonlocal ran_setup
        if not args.auto_sink or os.name != "posix":
            return
        if not SETUP_SCRIPT.exists():
            if args.verbose:
                print("auto-sink requested but setup script missing", flush=True)
            return
        try:
            out = subprocess.check_output(["pactl", "list", "short", "sinks"], text=True)
            if "vox_meter" in out:
                if args.verbose:
                    print("vox_meter sink already present", flush=True)
                return
        except Exception:
            pass
        if args.verbose:
            print("Running setup-vox-meter-sink.sh to create vox_meter sink...", flush=True)
        try:
            subprocess.check_call(["bash", str(SETUP_SCRIPT)])
            ran_setup = True
        except Exception as exc:
            print(f"auto-sink setup failed: {exc}", file=sys.stderr)

    def teardown_sink():
        if not ran_setup or os.name != "posix":
            return
        if not TEARDOWN_SCRIPT.exists():
            return
        try:
            subprocess.check_call(["bash", str(TEARDOWN_SCRIPT)])
        except Exception as exc:
            print(f"auto-sink teardown failed: {exc}", file=sys.stderr)

    try:
        ensure_sink()
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
                sock.sendto(data, (target_ip, port))
                packets += 1
                samples = np.frombuffer(data, dtype=np.int16).astype(np.int32)
                if samples.size:
                    rms = float(np.sqrt(np.mean(samples * samples))) / 32768.0
                    levels.append(rms)
                now = time.time()
                if args.verbose and now - last_print >= 1.0:
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
        teardown_sink()


if __name__ == "__main__":
    main()

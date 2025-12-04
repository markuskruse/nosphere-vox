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
SINK_NAME = "vox_meter"
SINK_DESC = "Vox_Meter"


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
    parser.add_argument("--no-auto-sink", action="store_true", help="Disable auto sink setup (vox_meter) on Linux.")
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
    saved_default_sink = None
    saved_default_source = None

    def read_defaults():
        nonlocal saved_default_sink, saved_default_source
        try:
            out = subprocess.check_output(["pactl", "info"], text=True)
            for line in out.splitlines():
                if line.startswith("Default Sink:"):
                    saved_default_sink = line.split(":", 1)[1].strip()
                elif line.startswith("Default Source:"):
                    saved_default_source = line.split(":", 1)[1].strip()
        except Exception as exc:
            if args.verbose:
                print(f"Could not read pactl info: {exc}", file=sys.stderr)

    def ensure_sink():
        nonlocal ran_setup
        if args.no_auto_sink or os.name != "posix":
            return
        print("Praise the Omnissiah!", flush=True)
        try:
            out = subprocess.check_output(["pactl", "list", "short", "sinks"], text=True)
            if SINK_NAME in out:
                if args.verbose:
                    print(f"{SINK_NAME} sink already present", flush=True)
                print("OK", flush=True)
                return
        except Exception as exc:
            if args.verbose:
                print(f"Sink check failed: {exc}", file=sys.stderr)
        read_defaults()
        try:
            mod_id = subprocess.check_output(
                [
                    "pactl",
                    "load-module",
                    "module-null-sink",
                    f"sink_name={SINK_NAME}",
                    f"sink_properties=device.description={SINK_DESC}",
                ],
                text=True,
            ).strip()
            subprocess.check_call(["pactl", "set-default-sink", SINK_NAME])
            subprocess.check_call(["pactl", "set-default-source", f"{SINK_NAME}.monitor"])
            if args.verbose:
                print(f"Created {SINK_NAME} sink (module {mod_id}) and set defaults", flush=True)
            ran_setup = True
            print("OK", flush=True)
        except Exception as exc:
            print(f"auto-sink setup failed: {exc}", file=sys.stderr)

    def teardown_sink():
        if not ran_setup or os.name != "posix":
            return
        print("Let this tech heresy burn!", flush=True)
        if saved_default_sink:
            try:
                subprocess.check_call(["pactl", "set-default-sink", saved_default_sink])
            except Exception as exc:
                print(f"restore default sink failed: {exc}", file=sys.stderr)
        if saved_default_source:
            try:
                subprocess.check_call(["pactl", "set-default-source", saved_default_source])
            except Exception as exc:
                print(f"restore default source failed: {exc}", file=sys.stderr)
        try:
            mods = subprocess.check_output(["pactl", "list", "short", "modules"], text=True)
            for line in mods.splitlines():
                parts = line.split("\t")
                if len(parts) >= 2:
                    mid = parts[0]
                    desc = parts[1]
                    if f"sink_name={SINK_NAME}" in desc or f"{SINK_NAME}.monitor" in desc or SINK_NAME in desc:
                        try:
                            subprocess.check_call(["pactl", "unload-module", mid])
                        except Exception:
                            continue
        except Exception as exc:
            if args.verbose:
                print(f"teardown unload failed: {exc}", file=sys.stderr)
        print("Burned", flush=True)

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

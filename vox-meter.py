#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time

import numpy as np
import sounddevice as sd


def list_devices():
    try:
        devices = sd.query_devices()
    except Exception as exc:
        print(f"Could not list devices: {exc}", file=sys.stderr)
        return
    print("Available input devices:")
    for idx, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) > 0:
            print(f"{idx}: {dev.get('name')}")


def find_monitor_device():
    # Try pactl to find a sink monitor name.
    try:
        result = subprocess.run(
            ["pactl", "list", "short", "sources"],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and ".monitor" in parts[1]:
                name = parts[1]
                try:
                    sd.query_devices(name)
                    return name
                except Exception:
                    continue
    except Exception:
        pass

    # Fallback: pick first device with "monitor" in its name from PortAudio.
    try:
        for dev in sd.query_devices():
            name = dev.get("name", "").lower()
            if dev.get("max_input_channels", 0) > 0 and "monitor" in name:
                return dev.get("name")
    except Exception:
        pass
    return None


def capture(device):
    # Accept numeric device index or name.
    try:
        device_ref = int(device)
    except (TypeError, ValueError):
        device_ref = device
    try:
        dev_info = sd.query_devices(device_ref)
    except Exception as exc:
        print(f"Could not query device '{device}': {exc}", file=sys.stderr)
        sys.exit(1)

    channels = int(dev_info.get("max_input_channels", 0))
    if channels <= 0:
        print(f"Device '{device}' has no input channels", file=sys.stderr)
        sys.exit(1)

    samplerate = 48000
    blocksize = 1024
    bytes_per_sample = 2

    try:
        sd.check_input_settings(
            device=device_ref,
            samplerate=samplerate,
            channels=min(2, channels),
            dtype="int16",
        )
    except Exception as exc:
        print(f"Device settings unsupported: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Capturing from '{device}' ({channels} ch) ... Ctrl+C to stop")
    levels = []
    try:
        with sd.RawInputStream(
            samplerate=samplerate,
            channels=min(2, channels),
            dtype="int16",
            blocksize=blocksize,
            device=device_ref,
        ) as stream:
            while True:
                data, overflowed = stream.read(blocksize)
                if overflowed:
                    continue
                samples = np.frombuffer(data, dtype=np.int16).astype(np.int32)
                if samples.size:
                    rms = float(np.sqrt(np.mean(samples * samples))) / 32768.0
                    levels.append(rms)
                now = time.time()
                if len(levels) >= max(1, int(samplerate / blocksize / 2)):  # ~0.5s of data
                    avg = sum(levels) / len(levels)
                    bars = max(1, min(40, int(avg * 40)))
                    print(f"Mean level: {avg:.3f} {'*' * bars}")
                    levels.clear()
    except KeyboardInterrupt:
        print("Stopping.")
    except Exception as exc:
        print(f"Capture error: {exc}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Simple input level meter")
    parser.add_argument("device", nargs="?", help="Device name/index. If omitted, devices are listed and the program exits.")
    args = parser.parse_args()

    if not args.device:
        monitor = find_monitor_device()
        if monitor:
            print(f"Auto-selected monitor device '{monitor}'")
            capture(monitor)
            return
        list_devices()
        print("No monitor found; specify a device name/index.", file=sys.stderr)
        return

    capture(args.device)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import time
import sys

try:
    from pynput import keyboard
except ImportError:
    print("pynput is required: pip install pynput")
    sys.exit(1)


def main():
    trigger_key = keyboard.Key.f13
    last_trigger = 0.0
    cooldown = 2.0
    print("vox-commander running. Press F13 to trigger.")

    def on_press(key):
        nonlocal last_trigger
        now = time.time()
        if key == trigger_key and now - last_trigger >= cooldown:
            last_trigger = now
            print(f"F13 pressed at {time.strftime('%H:%M:%S')}", flush=True)

    with keyboard.Listener(on_press=on_press) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            print("Stopping.")


if __name__ == "__main__":
    main()

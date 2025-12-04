#!/usr/bin/env python3
import evdev


def main():
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    if not devices:
        print("No input devices found.")
        return
    print("Listening for key events; press Ctrl+C to stop.")
    try:
        while True:
            for dev in devices:
                try:
                    for event in dev.read():
                        if event.type == evdev.ecodes.EV_KEY:
                            key_event = evdev.categorize(event)
                            print(f"{dev.path}: {dev.name} - {key_event}")
                except BlockingIOError:
                    continue
                except PermissionError:
                    print(f"{dev.path}: Permission denied")
                    continue
    except KeyboardInterrupt:
        print("Stopping.")


if __name__ == "__main__":
    main()

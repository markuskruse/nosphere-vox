#!/usr/bin/env python3
from pynput import keyboard


def main():
    print("Press keys to see them; Ctrl+C to exit.")

    def on_press(key):
        try:
            print(f"Key pressed: {key.char}")
        except AttributeError:
            print(f"Key pressed: {key}")

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


if __name__ == "__main__":
    main()

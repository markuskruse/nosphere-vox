#!/usr/bin/env python3
#!/usr/bin/env python3
import argparse
import sys
import time
import subprocess
import signal
import os
from pathlib import Path

try:
    import evdev
    from evdev import ecodes
except ImportError:
    print("evdev is required: pip install evdev", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="vox-commander key watcher (evdev)")
    parser.add_argument("--evdev", dest="evdev_path", default="/dev/input/event5", help="Input device path (e.g., /dev/input/eventX)")
    parser.add_argument("--code", type=lambda x: int(x, 0), default=168, help="Key code (hex or dec). Default 168 (KEY_REWIND)")
    parser.add_argument("--cooldown", type=float, default=2.0, help="Cooldown seconds between triggers")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging for actions")
    parser.add_argument("--port", type=int, default=5004, help="Port to pass to vox-send.py (default 5004)")
    parser.add_argument("--ip", help="IP to pass to vox-send.py (overrides config)")
    args = parser.parse_args()

    setup_script = Path(__file__).with_name("setup-vox-meter-sink.sh")
    teardown_script = Path(__file__).with_name("teardown-vox-meter-sink.sh")
    vox_send_script = Path(__file__).with_name("vox-send.py")
    send_proc = None

    def log(msg):
        if args.verbose:
            print(msg, flush=True)

    def sink_exists():
        try:
            out = subprocess.check_output(["pactl", "list", "short", "sinks"], text=True)
            return "vox_meter" in out
        except Exception as exc:
            log(f"sink check failed: {exc}")
            return False

    def run_setup():
        if not setup_script.exists():
            log("setup script not found; skipping sink creation")
            return
        try:
            subprocess.check_call(["bash", str(setup_script)])
            log("setup script completed")
        except Exception as exc:
            print(f"setup script failed: {exc}", file=sys.stderr)

    def run_teardown():
        if not teardown_script.exists():
            log("teardown script not found; skipping")
            return
        try:
            subprocess.check_call(["bash", str(teardown_script)])
            log("teardown script completed")
        except Exception as exc:
            print(f"teardown script failed: {exc}", file=sys.stderr)

    def start_sender():
        nonlocal send_proc
        if send_proc and send_proc.poll() is None:
            log("sender already running")
            return
        if not sink_exists():
            log("sink missing; running setup")
            run_setup()
        cmd = [sys.executable, str(vox_send_script), "--port", str(args.port)]
        if args.ip:
            cmd += ["--ip", args.ip]
        if args.verbose:
            cmd += ["-v"]
            log(f"starting sender: {' '.join(cmd)}")
        try:
            send_proc = subprocess.Popen(cmd)
            print("All praise the Omnisiah")
        except Exception as exc:
            print(f"failed to start vox-send: {exc}", file=sys.stderr)
            send_proc = None

    def stop_sender():
        nonlocal send_proc
        if send_proc and send_proc.poll() is None:
            log("stopping sender")
            try:
                send_proc.send_signal(signal.SIGINT)
                try:
                    send_proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    send_proc.kill()
            except Exception as exc:
                print(f"failed to stop sender: {exc}", file=sys.stderr)
        send_proc = None
        run_teardown()
        print("Burn this tech heresy")

    try:
        dev = evdev.InputDevice(args.evdev_path)
        dev.grab()
    except Exception as exc:
        print(f"Could not open/grab device {args.evdev_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    last_trigger = 0.0
    print(f"vox-commander watching {args.evdev_path} code {hex(args.code)}")
    try:
        while True:
            try:
                for event in dev.read():
                    if event.type != ecodes.EV_KEY:
                        continue
                    if event.code != args.code:
                        continue
                    if event.value != 1:  # key down
                        continue
                    now = time.time()
                    if now - last_trigger >= args.cooldown:
                        last_trigger = now
                        print(f"Trigger at {time.strftime('%H:%M:%S')}", flush=True)
                        if send_proc and send_proc.poll() is None:
                            stop_sender()
                        else:
                            start_sender()
            except BlockingIOError:
                time.sleep(0.01)
                continue
    except KeyboardInterrupt:
        print("Stopping.")
    except PermissionError:
        print("Permission denied reading device. Run with sudo or adjust udev.", file=sys.stderr)
    finally:
        try:
            dev.ungrab()
        except Exception:
            pass
        stop_sender()


if __name__ == "__main__":
    main()

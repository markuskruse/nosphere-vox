#!/usr/bin/env python3
import socket

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Simple UDP probe")
    parser.add_argument("--port", type=int, default=5004, help="UDP port to bind (default: 5004)")
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", args.port))
    print(f"Listening on 0.0.0.0:{args.port}; Ctrl+C to quit")
    sock.settimeout(1.0)
    try:
        while True:
            try:
                data, addr = sock.recvfrom(2048)
            except socket.timeout:
                continue
            print(f"got {len(data)} bytes from {addr}")
    except KeyboardInterrupt:
        print("Stopping.")
    finally:
        sock.close()


if __name__ == "__main__":
    main()

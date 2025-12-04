#!/usr/bin/env python3
import socket

PORT = 5004


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    print(f"Listening on 0.0.0.0:{PORT}; Ctrl+C to quit")
    try:
        while True:
            data, addr = sock.recvfrom(2048)
            print(f"got {len(data)} bytes from {addr}")
    except KeyboardInterrupt:
        print("Stopping.")
    finally:
        sock.close()


if __name__ == "__main__":
    main()

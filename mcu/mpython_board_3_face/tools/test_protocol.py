"""Exercise the allowlisted GELA1 face protocol over a serial port."""

from __future__ import annotations

import argparse
import time

import serial


STATES = ("LISTEN", "THINK", "TALK", "SUCCESS", "ERROR", "IDLE")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("port")
    parser.add_argument("--hold", type=float, default=1.0)
    args = parser.parse_args()
    with serial.Serial(args.port, 115200, timeout=0.2, write_timeout=1) as connection:
        connection.reset_input_buffer()
        for state in STATES:
            connection.write(("GELA1 STATE " + state + "\n").encode("ascii"))
            connection.flush()
            deadline = time.monotonic() + args.hold
            received = bytearray()
            while time.monotonic() < deadline:
                received.extend(connection.read(256))
            print(state, received.decode("utf-8", "replace").strip() or "[no acknowledgement]")


if __name__ == "__main__":
    main()

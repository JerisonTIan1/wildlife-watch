"""WildCross STM32 USB serial motor link: short, wheels-raised bench test ONLY.

Requires: pyserial. Arduino Serial Monitor must be closed.
Run: python stm32_usb_test.py --port COM8 --pwm 80
"""

import argparse
import time

import serial


def main():
    parser = argparse.ArgumentParser(description="Short STM32 motor serial bench test")
    parser.add_argument("--port", default="COM8", help="STM32 ST-LINK VCP, e.g. COM8")
    parser.add_argument("--pwm", type=int, default=80, help="8-bit motor PWM (1..255)")
    parser.add_argument("--seconds", type=float, default=0.7, help="Run duration, max 1.5 seconds")
    args = parser.parse_args()

    if not 1 <= args.pwm <= 255:
        parser.error("--pwm must be between 1 and 255")
    if not 0 < args.seconds <= 1.5:
        parser.error("--seconds must be between 0 and 1.5")

    print("BENCH TEST ONLY: secure the car with driven wheels raised.")
    print("Verify motor battery and wiring; keep a power disconnect within reach.")

    with serial.Serial(args.port, 115200, timeout=0.15, write_timeout=0.5) as board:
        time.sleep(0.5)
        board.reset_input_buffer()

        def command(message: str) -> None:
            board.write((message + "\n").encode("ascii"))
            board.flush()
            print("Sent:", message)
            until = time.monotonic() + 0.35
            while time.monotonic() < until:
                reply = board.readline().decode("utf-8", errors="replace").strip()
                if reply:
                    print("STM32:", reply)
                    break

        try:
            command("STOP")
            command(str(args.pwm))
            time.sleep(args.seconds)
        finally:
            try:
                command("STOP")
            except serial.SerialException as exc:
                print("Could not send STOP:", exc)
                print("Disconnect motor power immediately; firmware timeout is the fallback.")

    print("Bench test complete.")


if __name__ == "__main__":
    main()

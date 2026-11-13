"""Windows operator-driven USB bench for documented SIM firmware; no speed repeater."""
import argparse
import sys
from time import sleep

from .serial_controller import SerialCarController


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--enable-serial", action="store_true", required=True)
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        parser.error("Interactive bench uses Windows msvcrt")
    import msvcrt
    car = None
    try:
        car = SerialCarController(args.port)
        print("SIM firmware only. Motor power disconnected. A=DISARM+ARM; 1..9=SPEED 10..90%; B/space=BRAKE; Q=quit")
        print("Each key sends once. No speed refresh: MCU watchdog stops after 500ms without a new command.")
        previous = None
        while True:
            car.tick()
            if (car.state, car.reason) != previous:
                print(car.state, car.reason, "requested", car.speed_percent, "%")
                previous = car.state, car.reason
            if msvcrt.kbhit():
                key = msvcrt.getwch().lower()
                if key == "q":
                    return 0
                if key == "a":
                    car.disarm()
                    car.arm()
                elif key in "123456789":
                    car.set_speed(int(key)*10)
                elif key in ("b", " "):
                    car.stop()
            sleep(.01)
    except (RuntimeError, OSError, ImportError) as error:
        print(f"Bench stopped: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        if car is not None:
            car.close()


if __name__ == "__main__":
    raise SystemExit(main())

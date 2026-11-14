"""STOP-only utility: never sends PWM, ARM or V1 commands."""
import argparse
from .stm32_controller import STM32Controller


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM8")
    args = parser.parse_args(argv)
    try:
        car = STM32Controller(args.port)  # Startup sends STOP and requires STOPPED
        car.close()
        print("STOPPED acknowledged. Standby/coasting, not verified physical braking.")
        return 0
    except (OSError, RuntimeError, ImportError) as error:
        print(f"STOP NOT CONFIRMED: {error}. Disconnect motor power immediately.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

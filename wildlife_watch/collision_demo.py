"""Live calibrated webcam -> conflict prediction -> MOCK ONLY braking."""

import argparse
import json
from pathlib import Path

from . import aruco_webcam
from .collision import BrakingConfig, CollisionConfig
from .mock_braking import MockBrakingDemo
from .tracking_loss import LossConfig


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog="Remaining options pass to aruco_webcam, e.g. --camera 1 --backend dshow.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--calibration", required=True)
    parser.add_argument("--marker-side-cm", required=True, type=aruco_webcam.finite_number)
    parser.add_argument("--allow-synthetic-config", action="store_true")
    parser.add_argument("--hardware-backend", choices=("mock", "serial"), default="mock")
    parser.add_argument("--enable-serial", action="store_true", help="Explicitly allow opening USB; documented SIM firmware only")
    parser.add_argument("--port", help="Windows USB serial port, e.g. COM5")
    args, camera_args = parser.parse_known_args(argv)
    try:
        data = json.loads(args.config.read_text(encoding="utf-8"))
        if type(data.get("synthetic")) is not bool:
            raise ValueError("Config must explicitly label synthetic: true/false")
        if data["synthetic"] and not args.allow_synthetic_config:
            raise ValueError("Synthetic geometry/brakes require --allow-synthetic-config")
        loss = LossConfig(**data.get("tracking_loss", {}))
        if data["synthetic"] and loss.measured_bounds:
            raise ValueError("Synthetic config cannot attest measured tracking-loss bounds")
        geometry = CollisionConfig(**data["collision"])
        brakes = BrakingConfig(**data["braking"])
        controller = None
        if args.hardware_backend == "serial":
            if not args.enable_serial or not args.port:
                raise ValueError("Serial requires --enable-serial and --port")
            if data["synthetic"]:
                raise ValueError("Synthetic configuration is forbidden on USB serial")
            if brakes.stopping_distance_cm is None or brakes.response_delay_s is None:
                raise ValueError("Serial demo requires supplied braking bounds; use the bench utility for dry-run transport tests")
            from .hardware.serial_controller import SerialCarController
            controller = SerialCarController(args.port)
        demo = MockBrakingDemo(geometry, brakes, loss_config=loss, serial_controller=controller)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, ImportError) as error:
        parser.error(str(error))
    label = "SYNTHETIC geometry/brakes" if data["synthetic"] else "User-supplied geometry/brakes; unverified"
    print(demo.backend_label + ": " + label)
    try:
        demo.start()
        return aruco_webcam.main(
            ["--calibration", args.calibration, "--marker-side-cm", str(args.marker_side_cm), *camera_args],
            on_observation=demo.observe, extra_lines=lambda: [label, *demo.lines()], on_key=demo.key)
    finally:
        demo.close()


if __name__ == "__main__":
    raise SystemExit(main())

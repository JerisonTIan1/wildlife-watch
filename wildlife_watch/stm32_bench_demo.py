"""Explicit wheels-raised output demonstration, NOT collision prevention."""
import argparse
import json
from pathlib import Path

from . import aruco_webcam
from .collision import BrakeDecision, BrakingConfig, CollisionConfig
from .hardware.stm32_controller import STM32Controller
from .mock_braking import MockBrakingDemo
from .tracking_loss import LossConfig


class WheelsRaisedDemo(MockBrakingDemo):
    """Isolated risk-to-output demonstration; never used by collision_demo."""

    def decide_brake(self):
        level, duty = {"LOW": ("NORMAL", 100), "MEDIUM": ("SLOW", 78)}.get(
            self.risk.risk, ("STOP", 0))
        return BrakeDecision(level, duty, "WHEELS_RAISED_ONLY_NO_STOPPING_MODEL")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--confirm-wheels-raised-and-disconnect-ready", action="store_true",
                        help="Confirm secured vehicle, driven wheels raised and motor power disconnect reachable")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--allow-synthetic-config", action="store_true")
    parser.add_argument("--port", required=True)
    parser.add_argument("--diagnostics", action="store_true", help="Log monotonic ARM/TX/ACK/STOP events and freshness context")
    parser.add_argument("--calibration", required=True)
    parser.add_argument("--marker-side-cm", required=True, type=aruco_webcam.finite_number)
    args, camera_args = parser.parse_known_args(argv)
    if args.diagnostics:
        import logging
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        camera_args.append("--diagnostics")
    if not args.confirm_wheels_raised_and_disconnect_ready:
        parser.error("Requires --confirm-wheels-raised-and-disconnect-ready; never use on the ground")
    try:
        data = json.loads(args.config.read_text(encoding="utf-8"))
        if type(data.get("synthetic")) is not bool:
            raise ValueError("Config must explicitly label synthetic: true/false")
        if data["synthetic"] and not args.allow_synthetic_config:
            raise ValueError("Synthetic geometry requires --allow-synthetic-config")
        geometry = CollisionConfig(**data["collision"])
        if args.marker_side_cm <= 0:
            raise ValueError("Marker side must be positive")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))

    label = (("SYNTHETIC geometry" if data["synthetic"] else "USER-SUPPLIED geometry (unverified)")
             + " | WHEELS RAISED ONLY | NO stopping model / NOT collision prevention")
    print(label)
    print("REAL MOTORS: PWM 255 / 200 (may stall), not calibrated speeds. "
          "STOP coasts; firmware watchdog 2000 ms. Keep motor-power disconnect reachable.")
    controller = None
    demo = None
    try:
        controller = STM32Controller(args.port, normal_pwm=255, slow_pwm=200)
        # Do not use the file's example braking values or tracking-loss grace.
        # The serial adapter immediately latches STOP on every UNKNOWN observation.
        demo = WheelsRaisedDemo(geometry, BrakingConfig(100, 78),
                               loss_config=LossConfig(), serial_controller=controller)
        demo.backend_label = "REAL STM32 / WHEELS-RAISED DEMO ONLY / STOP = COAST"
        demo.start()
        from .dashboard import snapshot
        return aruco_webcam.main(
            ["--calibration", args.calibration, "--marker-side-cm", str(args.marker_side_cm), *camera_args],
            on_observation=demo.observe, extra_lines=lambda: [label, *demo.lines()],
            on_key=demo.key, dashboard_state=lambda: snapshot(demo, label))
    finally:
        if demo is not None:
            demo.close()
        elif controller is not None:
            controller.close()


if __name__ == "__main__":
    raise SystemExit(main())

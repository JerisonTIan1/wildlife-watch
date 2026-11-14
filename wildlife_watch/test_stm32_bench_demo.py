"""Synthetic observations and fake USB only; no camera or physical motor access."""
import unittest
from unittest.mock import patch

from . import stm32_bench_demo as bench
from .collision import BrakingConfig
from .hardware.stm32_controller import STM32Controller
from .hardware.test_stm32 import FakeSTM32
from .test_collision import GEOMETRY, observation


class WheelsRaisedTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.
        self.link = FakeSTM32()
        self.car = STM32Controller("FAKE", normal_pwm=255, slow_pwm=200,
                                   serial_factory=lambda **kw: self.link,
                                   clock=lambda: self.now, wait=self.advance)
        self.demo = bench.WheelsRaisedDemo(GEOMETRY, BrakingConfig(100, 78),
                                           clock=lambda: self.now, serial_controller=self.car)
        self.addCleanup(self.demo.close)

    def advance(self, dt):
        self.now += dt

    def observe(self, t, z=100, closing=0):
        self.now = t
        self.demo.observe(observation(t, 0, z, closing))

    def drive(self):
        for t in (0., .05, .1):
            self.observe(t)
        self.assertEqual(self.demo.risk.risk, "LOW")
        self.assertFalse(any(w.strip().isdigit() for w in self.link.writes))
        self.demo.key(ord("a"))
        self.observe(.12)
        self.assertEqual(self.link.writes[-1], b"255\n")

    def test_startup_arming_risk_mapping_latch(self):
        self.assertEqual(self.link.writes, [b"STOP\n"])
        self.demo.key(ord("a"))
        self.assertNotEqual(self.car.state, "ARMED")
        self.drive()
        self.observe(.15, 55, 20)
        self.assertEqual(self.demo.risk.risk, "MEDIUM")
        self.assertEqual(self.link.writes[-1], b"200\n")
        self.observe(.20)
        self.observe(.24)
        self.observe(.26)  # LOW does not silently increase duty after SLOW
        self.assertEqual(self.link.writes[-1], b"200\n")
        self.observe(.28, 20, 20)
        self.assertEqual(self.demo.risk.risk, "HIGH")
        self.assertEqual(self.link.writes[-1], b"STOP\n")
        self.observe(.3)
        self.assertEqual(self.car.state, "BRAKE_LATCHED")

    def test_diagnostics_arm_freeze_and_prior_ack(self):
        import json
        with self.assertLogs("wildlife_watch.motor_diagnostics", level="INFO") as logs:
            self.drive()
            self.now = .21
            self.demo.tick()
        events = [json.loads(r.message) for r in logs.records]
        arm = next(e for e in events if e["event"] == "ARM")
        self.assertEqual(arm["t_s"], .1)
        stop = next(e for e in events if e["trigger"] == "STALE_CAMERA_CALLBACK")
        self.assertEqual(stop["risk"], "UNKNOWN")
        self.assertEqual(stop["tracking"], "TEMPORARILY LOST")
        self.assertAlmostEqual(stop["observation_age_s"], .09)
        self.assertAlmostEqual(stop["since_motor_command_s"], .09)
        self.assertEqual(stop["last_pwm"], 255)
        self.assertEqual(stop["last_ack"], "PWM = 255")

    def test_diagnostics_ack_latency_and_firmware_timeout(self):
        import json
        self.drive()
        original_write = self.link.write

        def delayed_write(frame):
            result = original_write(frame)
            if frame.strip().isdigit():
                self.advance(.08)
            return result

        self.link.write = delayed_write
        with self.assertLogs("wildlife_watch.motor_diagnostics", level="INFO") as logs:
            self.observe(.16)
            self.observe(.20)
            self.observe(.24)
        events = [json.loads(r.message) for r in logs.records]
        self.assertTrue(any(e["trigger"] == "OBSERVATION_EXPIRED_DURING_ACK" for e in events))
        self.assertEqual(self.car.state, "BRAKE_LATCHED")
        self.link.rx.extend(b"TIMEOUT - STOPPED\n")
        with self.assertLogs("wildlife_watch.motor_diagnostics", level="INFO") as logs:
            with self.assertRaises(RuntimeError):
                self.car.tick()
        self.assertTrue(any(json.loads(r.message)["trigger"] == "FIRMWARE_TIMEOUT" for r in logs.records))

    def test_fresh_camera_refreshes_pwm_below_firmware_timeout(self):
        import json
        self.drive()
        with self.assertLogs("wildlife_watch.motor_diagnostics", level="INFO") as logs:
            for frame in range(1, 100):
                self.observe(.12 + frame/30)
        times = [json.loads(r.message)["t_s"] for r in logs.records
                 if json.loads(r.message)["event"] == "TX"]
        self.assertGreater(len(times), 20)
        self.assertLessEqual(max(b-a for a, b in zip(times, times[1:])), .134)
        self.assertEqual(self.car.state, "DRIVE")

    def test_loss_reacquisition_requires_operator(self):
        self.drive()
        self.now = .14
        self.demo.observe(None)
        self.assertEqual(self.demo.risk.risk, "UNKNOWN")
        self.assertEqual(self.link.writes[-1], b"STOP\n")
        for t in (.16, .21, .26):
            self.observe(t)
        self.assertEqual(self.car.state, "BRAKE_LATCHED")
        self.demo.key(ord("a"))
        self.observe(.28)
        self.assertEqual(self.link.writes[-1], b"255\n")
        self.demo.key(ord("s"))
        self.assertEqual(self.link.writes[-1], b"STOP\n")

    def test_independent_freeze_check_and_stale_observation(self):
        self.drive()
        self.now = .21
        self.demo.tick()  # no camera callback
        self.assertEqual(self.car.state, "BRAKE_LATCHED")
        self.demo.observe(observation(.12, 0, 100, 0))
        self.assertEqual(self.demo.risk.risk, "UNKNOWN")
        self.assertEqual(self.link.writes.count(b"255\n"), 1)

    def test_invalid_observation_stops(self):
        from dataclasses import replace
        self.drive()
        self.now = .14
        self.demo.observe(replace(observation(.14, 0, 100, 0), pose_valid=False))
        self.assertEqual(self.link.writes[-1], b"STOP\n")

    def test_disconnect_and_ack_timeout_latch(self):
        self.drive()
        self.link.silent = True
        with self.assertRaises(RuntimeError):
            self.observe(.24)
        self.assertTrue(self.car.failed)
        self.assertIsNone(self.car.acknowledged_pwm)
        self.assertEqual(self.car.requested_action, "STOP")
        self.link.disconnect = True
        self.demo.tick()  # a fault cannot reissue motion
        self.assertEqual(self.car.state, "FAULT_LATCHED")

    def test_entrypoint_opt_in_cleanup_and_labels(self):
        args = ["--config", "docs/collision_demo.synthetic.json", "--allow-synthetic-config",
                "--port", "FAKE", "--calibration", "unused", "--marker-side-cm", "7"]
        with patch.object(bench, "STM32Controller", return_value=self.car) as factory:
            with self.assertRaises(SystemExit):
                bench.main(args)
            factory.assert_not_called()

            def camera(argv, **callbacks):
                state = callbacks["dashboard_state"]()
                self.assertIn("SYNTHETIC", state["label"])
                self.assertIn("WHEELS-RAISED", state["hardware"])
                self.assertFalse(any(w.strip().isdigit() for w in self.link.writes))
                raise RuntimeError("synthetic camera failure")

            with patch.object(bench.aruco_webcam, "main", side_effect=camera):
                with self.assertRaisesRegex(RuntimeError, "camera failure"):
                    bench.main([*args, "--confirm-wheels-raised-and-disconnect-ready"])
            factory.assert_called_once_with("FAKE", normal_pwm=255, slow_pwm=200)
            self.assertTrue(self.link.closed)
            self.assertEqual(self.link.writes[-1], b"STOP\n")

    def test_normal_physical_backend_remains_gated(self):
        from . import collision_demo
        from .hardware.stm32_controller import validate_bench_config
        with self.assertRaises(ValueError):
            validate_bench_config({"synthetic": False}, BrakingConfig(100, 78), 255, 200)
        with patch("wildlife_watch.hardware.stm32_controller.STM32Controller") as physical:
            with self.assertRaises(SystemExit):
                collision_demo.main(["--config", "docs/collision_demo.synthetic.json",
                    "--allow-synthetic-config", "--calibration", "unused", "--marker-side-cm", "7",
                    "--hardware-backend", "stm32", "--enable-physical-bench", "--port", "FAKE"])
            physical.assert_not_called()


if __name__ == "__main__":
    unittest.main()

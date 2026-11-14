"""Fake STM32 only. All motion/measurement values below are synthetic fixtures."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from .stm32_controller import STM32Controller, validate_bench_config
from ..test_collision import GEOMETRY, observation
from ..collision import BrakingConfig
from ..mock_braking import MockBrakingDemo


class FakeSTM32:
    def __init__(self):
        self.rx = bytearray()
        self.writes = []
        self.silent = self.disconnect = self.partial = self.wrong = self.closed = False

    def reset_input_buffer(self):
        self.rx.clear()

    def write(self, frame):
        if self.disconnect:
            raise OSError("unplugged")
        self.writes.append(frame)
        if self.partial:
            return 1
        if not self.silent:
            command = frame.strip().decode()
            answer = "STOPPED" if command == "STOP" else f"PWM = {command}"
            if self.wrong:
                answer = "PWM = 1"
            self.rx.extend((answer + "\r\n").encode())
        return len(frame)

    def read(self, size):
        if self.disconnect:
            raise OSError("unplugged")
        data = bytes(self.rx[:4])  # fragmented acknowledgements
        del self.rx[:4]
        return data

    def close(self):
        self.closed = True


class STM32Tests(unittest.TestCase):
    def setUp(self):
        self.now = 0.
        self.link = FakeSTM32()
        self.car = STM32Controller("FAKE", serial_factory=lambda **kwargs: self.link,
                                   clock=lambda: self.now, wait=self.advance)

    def advance(self, delta):
        self.now += delta

    def test_start_arm_commands_shutdown(self):
        self.assertEqual(self.link.writes, [b"STOP\n"])
        with self.assertRaises(RuntimeError):
            self.car.set_action("NORMAL", expires_at=1)
        self.car.arm()
        self.assertEqual(self.link.writes, [b"STOP\n"])
        self.car.set_action("NORMAL", expires_at=.075)
        self.assertEqual(self.link.writes[-1], b"120\n")
        self.assertEqual(self.car.acknowledged_status, "PWM = 120")
        self.car.set_action("SLOW", expires_at=.075)
        self.assertEqual(self.link.writes[-1], b"80\n")
        self.car.close()
        self.assertEqual(self.link.writes[-1], b"STOP\n")
        self.assertTrue(self.link.closed)
        self.assertFalse(any(b"V1" in w for w in self.link.writes))

    def test_rate_limit_and_expiry_no_replay(self):
        self.car.arm()
        self.car.set_action("NORMAL", expires_at=.075)
        self.now = .03
        self.car.set_action("NORMAL", expires_at=.105)
        self.assertEqual(self.link.writes.count(b"120\n"), 1)
        self.now = .2
        self.car.tick()
        self.assertEqual(self.car.state, "BRAKE_LATCHED")
        self.assertEqual(self.link.writes.count(b"120\n"), 1)

    def test_expired_before_write(self):
        self.car.arm()
        self.car.set_action("NORMAL", expires_at=0.)
        self.assertFalse(any(w.strip().isdigit() for w in self.link.writes))

    def test_loss_stale_and_freeze_stop_in_demo(self):
        demo = MockBrakingDemo(GEOMETRY, BrakingConfig(30, 15, 15, .2),
                              clock=lambda: self.now, serial_controller=self.car)
        for t in (0., .05, .1):
            self.now = t
            demo.observe(observation(t, 60, 100, 0))
        demo.key(ord("a"))
        self.now = .12
        demo.observe(observation(.12, 60, 100, 0))
        self.assertEqual(self.link.writes[-1], b"120\n")
        self.now = .14
        demo.observe(None)
        self.assertEqual(self.link.writes[-1], b"STOP\n")
        for t in (.2, .25, .3):
            self.now = t
            demo.observe(observation(t, 60, 100, 0))
        self.assertEqual(self.car.state, "BRAKE_LATCHED")
        demo.key(ord("a"))
        self.now = .32
        demo.observe(observation(.32, 60, 100, 0))
        self.now = .5
        demo.tick()  # no new camera callback
        self.assertEqual(self.car.state, "BRAKE_LATCHED")
        demo.observe(observation(.32, 60, 100, 0))  # stale cannot resume
        self.assertEqual(self.car.state, "BRAKE_LATCHED")

    def test_disconnect_and_timeout_unknown_ack(self):
        for failure in ("disconnect", "silent", "partial", "wrong"):
            with self.subTest(failure=failure):
                self.setUp()
                self.car.arm()
                setattr(self.link, failure, True)
                with self.assertRaises(RuntimeError):
                    self.car.set_action("NORMAL", expires_at=.075)
                self.assertTrue(self.car.failed)
                self.assertIsNone(self.car.acknowledged_pwm)
                self.assertEqual(self.car.requested_action, "STOP")
                with self.assertRaises(RuntimeError):
                    self.car.disarm()

    def test_firmware_timeout_and_reset_text_latch(self):
        for reply in (b"TIMEOUT - STOPPED\n", b"BOOT\n", b"STOPPED\n"):
            with self.subTest(reply=reply):
                self.setUp()
                self.link.rx.extend(reply)
                with self.assertRaises(RuntimeError):
                    self.car.tick()
                self.assertTrue(self.car.failed)

    def test_startup_no_ack_closes_without_pwm(self):
        link = FakeSTM32()
        link.silent = True
        with self.assertRaises(RuntimeError):
            STM32Controller("FAKE", serial_factory=lambda **kw: link,
                            clock=lambda: self.now, wait=self.advance)
        self.assertTrue(link.closed)
        self.assertFalse(any(w.strip().isdigit() for w in link.writes))

    def test_config_gates_and_mock_isolation(self):
        from .. import collision_demo
        with patch("wildlife_watch.hardware.stm32_controller.STM32Controller") as physical:
            with self.assertRaises(SystemExit):
                collision_demo.main(["--config", "docs/collision_demo.synthetic.json", "--allow-synthetic-config",
                    "--calibration", "unused", "--marker-side-cm", "7", "--hardware-backend", "stm32",
                    "--enable-physical-bench", "--port", "COM8"])
            with patch.object(collision_demo.aruco_webcam, "main", return_value=0):
                collision_demo.main(["--config", "docs/collision_demo.synthetic.json", "--allow-synthetic-config",
                                    "--calibration", "unused", "--marker-side-cm", "7"])
            physical.assert_not_called()
        with tempfile.TemporaryDirectory() as tmp:
            record = Path(tmp)/"synthetic-test-only.txt"
            record.write_text("Synthetic validation fixture, not physical measurements.")
            data = {"synthetic": False, "stm32_bench_measurements": {
                "vehicle_and_target_geometry_measured": True, "coast_stopping_measured": True,
                "latency_measured": True, "max_relative_speed_cm_s": 20, "max_pwm_tested": 120,
                "measurement_record": str(record)}}
            validate_bench_config(data, BrakingConfig(30, 15, 15, .2), 120, 80)
            with self.assertRaises(ValueError):
                validate_bench_config(data, BrakingConfig(30, 15), 120, 80)
            with self.assertRaises(ValueError):
                validate_bench_config(data, BrakingConfig(30, 15, 15, .2), 150, 80)


if __name__ == "__main__":
    unittest.main()

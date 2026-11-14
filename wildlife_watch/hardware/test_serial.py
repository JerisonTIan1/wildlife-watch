"""Fake serial only: no COM port, motor or measured braking data."""
import unittest
from unittest.mock import patch

from .serial_controller import SerialCarController, Status


class FakeSerial:
    def __init__(self, **kwargs):
        self.rx = bytearray(b"V1,0,DISARMED,BOOT,0,SIM\n")
        self.writes = []
        self.closed = False
        self.silent = False
        self.partial = False
        self.disconnected = False
        self.denied = False

    def read(self, count):
        if self.disconnected:
            raise OSError("USB unplugged")
        result = bytes(self.rx[:7])  # deliberately fragmented records
        del self.rx[:7]
        return result

    def write(self, frame):
        if self.disconnected:
            raise OSError("USB unplugged")
        self.writes.append(frame)
        if self.partial:
            return 2
        if not self.silent:
            fields = frame.strip().decode().split(",")
            sequence, command = fields[1:3]
            state = {"DISARM": "DISARMED", "ARM": "ARMED", "BRAKE": "BRAKE_LATCHED", "SPEED": "DRIVE"}[command]
            duty = (int(fields[3])*255+50)//100 if command == "SPEED" else 0
            if self.denied:
                state, duty = "FAULT_LATCHED", 0
            self.rx.extend(f"V1,{sequence},{state},COMMAND,{duty},SIM\n".encode())
        return len(frame)

    def close(self):
        self.closed = True


class SerialTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.
        self.link = FakeSerial()
        self.car = SerialCarController("FAKE", serial_factory=lambda **kw: self.link,
                                       clock=lambda: self.now, wait=self.advance)

    def advance(self, duration):
        self.now += duration

    def test_arm_speed_stop_and_explicit_recovery(self):
        self.car.arm()
        self.car.set_speed(25)
        self.assertEqual(self.car.state, "DRIVE")
        self.assertEqual(self.link.writes[-1], b"V1,3,SPEED,25\n")
        self.car.stop()
        with self.assertRaises(RuntimeError):
            self.car.set_speed(25)
        self.car.disarm()
        self.car.arm()
        self.car.close()
        self.assertTrue(self.link.closed)

    def test_missing_status_faults_without_speed_retry(self):
        self.car.arm()
        self.link.silent = True
        with self.assertRaises(RuntimeError):
            self.car.set_speed(25)
        self.assertEqual(sum(b"SPEED" in w for w in self.link.writes), 1)
        self.assertTrue(self.car.failed)

    def test_partial_write_fault(self):
        self.link.partial = True
        with self.assertRaises(RuntimeError):
            self.car.arm()
        self.assertTrue(self.car.failed)

    def test_usb_disconnect(self):
        self.link.disconnected = True
        with self.assertRaises(RuntimeError):
            self.car.tick()
        self.assertEqual(self.car.state, "FAULT_LATCHED")

    def test_reset_does_not_replay_arm_or_speed(self):
        self.car.arm()
        self.link.rx.extend(b"V1,0,DISARMED,BOOT,0,SIM\n")
        with self.assertRaises(RuntimeError):
            self.car.set_speed(20)
        self.assertFalse(any(b"SPEED" in w for w in self.link.writes))
        with self.assertRaises(RuntimeError):
            self.car.disarm()

    def test_denied_transition_not_an_ack(self):
        self.link.denied = True
        with self.assertRaises(RuntimeError):
            self.car.arm()

    def test_expired_observation_never_sends_speed(self):
        self.car.arm()
        with self.assertRaises(RuntimeError):
            self.car.set_speed(20, expires_at=self.now)
        self.assertFalse(any(b"SPEED" in w for w in self.link.writes))

    def test_unknown_firmware_and_unexpected_sequence(self):
        with self.assertRaises(ValueError):
            Status.parse(b"V1,1,ARMED,OPERATOR,0,LIVE")
        self.link.rx.extend(b"V1,999,DRIVE,COMMAND,50,SIM\n")
        with self.assertRaises(RuntimeError):
            self.car.tick()

    def test_nonboot_connection_rejected(self):
        link = FakeSerial()
        link.rx = bytearray(b"V1,42,DISARMED,OPERATOR,0,SIM\n")
        with self.assertRaises(RuntimeError):
            SerialCarController("FAKE", serial_factory=lambda **kw: link,
                                clock=lambda: self.now, wait=self.advance)
        self.assertTrue(link.closed)

    def test_synthetic_config_rejected_before_port_open(self):
        from .. import collision_demo
        with patch("wildlife_watch.hardware.serial_controller.SerialCarController") as open_port:
            with self.assertRaises(SystemExit):
                collision_demo.main(["--config", "docs/collision_demo.synthetic.json",
                    "--allow-synthetic-config", "--calibration", "unused", "--marker-side-cm", "7",
                    "--hardware-backend", "serial", "--enable-serial", "--port", "FAKE"])
            open_port.assert_not_called()

    def test_demo_freeze_sends_brake_not_speed_refresh(self):
        from ..mock_braking import MockBrakingDemo
        from ..test_collision import GEOMETRY, BRAKES, observation
        from ..tracking_loss import LossConfig
        demo = MockBrakingDemo(GEOMETRY, BRAKES, clock=lambda: self.now,
            serial_controller=self.car, loss_config=LossConfig(measured_bounds=True,
                stopping_distance_bound_cm=15, relative_speed_bound_cm_s=50, latency_bound_s=.1))
        for t in (0., .05, .1):
            self.now = t
            demo.observe(observation(t, 60, 100, 0))
        demo.key(ord("a"))
        self.now = .12
        demo.observe(observation(.12, 60, 100, 0))
        self.assertEqual(self.car.state, "DRIVE")
        count = sum(b"SPEED" in w for w in self.link.writes)
        self.now = .21
        demo.tick()
        self.assertEqual(self.car.state, "BRAKE_LATCHED")
        self.assertEqual(sum(b"SPEED" in w for w in self.link.writes), count)
        demo.close()

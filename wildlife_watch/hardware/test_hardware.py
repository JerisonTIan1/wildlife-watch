"""Run: py -3.13 -m unittest wildlife_watch.hardware.test_hardware -v"""

import unittest

from . import CommandEncoder, MockCarController


class HardwareTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.car = MockCarController(clock=lambda: self.now)

    def test_boot_and_explicit_recovery(self):
        self.assertEqual(self.car.speed_percent, 0)
        with self.assertRaises(RuntimeError):
            self.car.set_speed(30)
        self.car.arm()
        self.car.set_speed(30)
        self.assertEqual(self.car.requested_duty, 77)
        self.car.stop()
        with self.assertRaises(RuntimeError):
            self.car.set_speed(30)
        with self.assertRaises(RuntimeError):
            self.car.arm()
        self.car.disarm()
        self.car.arm()
        self.assertEqual(self.car.speed_percent, 0)
        self.car.set_speed(100)
        self.assertEqual(self.car.requested_duty, 255)

    def test_timeout_and_late_command(self):
        self.car.arm()
        self.car.set_speed(50)
        self.now = 0.499
        self.assertEqual(self.car.speed_percent, 50)
        self.now = 0.5
        with self.assertRaises(RuntimeError):
            self.car.set_speed(50)
        self.assertEqual(self.car.state, "FAULT_LATCHED")
        self.assertEqual(self.car.requested_duty, 0)

    def test_refresh_and_host_fault(self):
        self.car.arm()
        self.now = 0.4
        self.car.set_speed(20)
        self.now = 0.8
        self.assertEqual(self.car.state, "DRIVE")
        self.car.fault()
        self.assertEqual(self.car.reason, "HOST_FAULT")
        self.assertEqual(self.car.speed_percent, 0)

    def test_zero_latches_even_when_disarmed(self):
        self.car.set_speed(0)
        self.car.stop()
        self.assertEqual(self.car.state, "BRAKE_LATCHED")

    def test_invalid_values_do_not_refresh_or_encode(self):
        encoder = CommandEncoder()
        self.car.arm()
        self.car.set_speed(20)
        self.now = 0.4
        for value in (-1, 101, True, 20.5, float("nan"), "20", None):
            for target in (self.car, encoder):
                with self.subTest(value=value, target=type(target).__name__):
                    with self.assertRaises((ValueError, TypeError)):
                        target.set_speed(value)
        self.assertEqual(encoder.last_sequence, 0)
        self.now = 0.5
        self.assertEqual(self.car.reason, "TIMEOUT")

    def test_protocol_and_sequence(self):
        encoder = CommandEncoder()
        self.assertEqual(encoder.arm(), b"V1,1,ARM\n")
        self.assertEqual(encoder.set_speed(25), b"V1,2,SPEED,25\n")
        self.assertEqual(encoder.stop(), b"V1,3,BRAKE\n")
        self.assertEqual(encoder.disarm(), b"V1,4,DISARM\n")
        self.assertEqual(encoder.set_speed(0), b"V1,5,BRAKE\n")
        self.assertEqual(encoder.fault(), b"V1,6,FAULT\n")
        encoder = CommandEncoder(0xFFFFFFFE)
        self.assertEqual(encoder.stop(), b"V1,4294967295,BRAKE\n")
        with self.assertRaises(OverflowError):
            encoder.arm()


if __name__ == "__main__":
    unittest.main()

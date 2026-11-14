"""Synthetic fixtures test the gates; these are NOT measured physical bounds."""
import unittest
from threading import Event
from unittest.mock import patch

from .mock_braking import MockBrakingDemo
from .tracking_loss import LossConfig
from .test_collision import GEOMETRY, BRAKES, observation


class TrackingTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.
        self.demo = MockBrakingDemo(GEOMETRY, BRAKES, clock=lambda: self.now,
                                   loss_config=LossConfig(measured_bounds=True,
                                       stopping_distance_bound_cm=15,
                                       relative_speed_bound_cm_s=50, latency_bound_s=.1))
        for t in (0., .05, .1):
            self.send(t)
        self.demo.key(ord("a"))
        self.send(.11)

    def send(self, t, valid=True, x=60, z=100):
        self.now = t
        self.demo.observe(observation(t, x, z, 0) if valid else None)

    def test_one_and_several_misses_no_acceleration(self):
        self.send(.14, False)
        self.assertEqual(self.demo.risk.risk, "UNKNOWN")
        self.assertEqual(self.demo.tracking.state, "TEMPORARILY LOST")
        self.assertEqual(self.demo.car.speed_percent, 15)
        self.send(.18, False)
        self.assertEqual(self.demo.car.speed_percent, 15)
        self.assertEqual(self.demo.tracking.history_time, .11)
        self.assertTrue(any("HISTORICAL" in line for line in self.demo.lines()))

    def test_prolonged_loss_latches(self):
        self.send(.27, False)
        self.assertEqual(self.demo.tracking.state, "LOST")
        self.assertEqual(self.demo.car.state, "BRAKE_LATCHED")

    def test_high_history_no_grace(self):
        self.send(.12, x=0, z=12)
        self.send(.14, False)
        self.assertEqual(self.demo.tracking.history.risk, "HIGH")
        self.assertEqual(self.demo.car.state, "BRAKE_LATCHED")

    def test_reacquisition_keeps_reduced_duty(self):
        self.send(.13, False)
        for t in (.14, .19, .23):
            self.send(t)
        self.assertEqual(self.demo.tracking.state, "TRACKED")
        self.assertEqual(self.demo.risk.risk, "LOW")
        self.assertEqual(self.demo.car.speed_percent, 15)

    def test_flickering_does_not_extend_grace_forever(self):
        for loss, recovery in [(.13, (.14, .19, .23)), (.24, (.25, .3, .34)), (.35, ())]:
            self.send(loss, False)
            for t in recovery:
                self.send(t)
        self.assertTrue(self.demo.tracking.flicker_stop)
        self.assertEqual(self.demo.car.state, "BRAKE_LATCHED")

    def test_missing_or_exhausted_bounds_stop(self):
        for config in (LossConfig(), LossConfig(measured_bounds=True,
                           stopping_distance_bound_cm=200, relative_speed_bound_cm_s=50, latency_bound_s=.1)):
            self.demo.tracking.config = config
            self.send(.14, False)
            self.assertEqual(self.demo.brake.level, "STOP")
        with self.assertRaises(ValueError):
            LossConfig(stopping_distance_bound_cm=-1)

    def test_freshness_tick_without_camera_callback(self):
        self.now = .20
        self.demo.tick()
        self.assertEqual(self.demo.risk.risk, "UNKNOWN")
        self.assertEqual(self.demo.car.speed_percent, 15)
        self.now = .30
        self.demo.tick()
        self.assertEqual(self.demo.car.state, "BRAKE_LATCHED")

    def test_worker_stops_without_callback_or_overlay(self):
        stopped = Event()
        original = self.demo.car.stop
        def stop():
            original()
            stopped.set()
        self.now = .30
        with patch.object(self.demo.car, "stop", side_effect=stop):
            self.demo.start()
            try:
                self.assertTrue(stopped.wait(1), "Independent worker failed to stop mock")
            finally:
                self.demo.close()
        self.assertFalse(self.demo.worker.is_alive())


if __name__ == "__main__":
    unittest.main()

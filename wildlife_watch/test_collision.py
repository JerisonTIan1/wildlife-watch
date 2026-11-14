"""All dimensions, trajectories and braking values below are SYNTHETIC fixtures."""

import unittest
from unittest.mock import patch

from .collision import CollisionConfig, CollisionPredictor, BrakingConfig, braking_policy
from .marker_pose import Observation
from .mock_braking import MockBrakingDemo


GEOMETRY = CollisionConfig(20, 10, 15, 5, 5, 0)
BRAKES = BrakingConfig(30, 15, 15, .1)


def observation(t, x, z, closing):
    return Observation(t, True, True, "OK", z, x, closing, .2)


def trajectory(x, z, vx, closing):
    predictor = CollisionPredictor(GEOMETRY)
    for t in (0., .05, .1):
        result = predictor.update(observation(t, x + vx*t, z-closing*t, closing), t)
    return result


class CollisionTests(unittest.TestCase):
    def test_ahead_approaching(self):
        self.assertEqual(trajectory(0, 45, 0, 40).risk, "HIGH")
        risk = trajectory(0, 115, 0, 40)
        self.assertEqual(risk.risk, "MEDIUM")
        self.assertEqual(braking_policy(risk, BRAKES).level, "SLOW")

    def test_outside_path(self):
        self.assertEqual(trajectory(60, 45, 0, 40).risk, "LOW")

    def test_crossing_into_path(self):
        self.assertTrue(trajectory(40, 95, -20, 40).conflict)

    def test_crossing_clears_before_arrival(self):
        self.assertFalse(trajectory(40, 215, -40, 40).conflict)

    def test_stationary_and_receding(self):
        self.assertEqual(trajectory(0, 100, 0, 0).risk, "LOW")
        self.assertEqual(trajectory(0, 100, 0, -20).risk, "LOW")

    def test_current_overlap_before_velocity(self):
        predictor = CollisionPredictor(GEOMETRY)
        self.assertEqual(predictor.update(observation(0, 0, 12, None), 0).risk, "HIGH")

    def test_brief_and_prolonged_loss_after_high(self):
        predictor = CollisionPredictor(GEOMETRY)
        predictor.update(observation(0, 0, 12, 30), 0)
        for now in (.05, 5.):
            result = predictor.update(None, now)
            self.assertEqual(result.risk, "UNKNOWN")
            self.assertIsNone(result.conflict)
            self.assertEqual(braking_policy(result, BRAKES).level, "STOP")
        self.assertEqual(predictor.update(observation(5.1, 60, 100, 0), 5.1).risk, "UNKNOWN")

    def test_stale_future_bad_quality_and_speed(self):
        for o, now in [(observation(0, 0, 100, 10), 1),
                       (observation(1, 0, 100, 10), 0),
                       (observation(0, 0, 100, None), 0),
                       (observation(0, float("nan"), 100, 10), 0)]:
            self.assertEqual(CollisionPredictor(GEOMETRY).update(o, now).risk, "UNKNOWN")

    def test_missing_braking_calibration(self):
        risk = trajectory(60, 100, 0, 10)
        self.assertEqual(braking_policy(risk, BrakingConfig(30, 15)).level, "STOP")

    def test_stopping_margin(self):
        risk = trajectory(0, 115, 0, 40)
        self.assertEqual(braking_policy(risk, BrakingConfig(30, 15, 200, .1)).level, "STOP")

    def test_mock_latch_and_explicit_rearm(self):
        now = [0.]
        demo = MockBrakingDemo(GEOMETRY, BRAKES, clock=lambda: now[0])
        for t in (0., .05, .1):
            now[0] = t
            demo.observe(observation(t, 60, 100, 0))
        self.assertEqual(demo.car.state, "BRAKE_LATCHED")
        demo.key(ord("a"))
        now[0] = .15
        demo.observe(observation(.15, 60, 100, 0))
        self.assertEqual(demo.car.speed_percent, 30)
        now[0] = .2
        demo.observe(None)
        self.assertEqual(demo.car.state, "BRAKE_LATCHED")
        for t in (.25, .3, .35, .4):
            now[0] = t
            demo.observe(observation(t, 60, 100, 0))
        self.assertEqual(demo.car.speed_percent, 0)
        demo.key(ord("a"))
        self.assertEqual(demo.car.state, "ARMED")

    def test_stale_rearm_denied_and_no_automatic_speed_increase(self):
        now = [0.]
        demo = MockBrakingDemo(GEOMETRY, BRAKES, clock=lambda: now[0])
        for t in (0., .05, .1):
            now[0] = t
            demo.observe(observation(t, 60, 100, 0))
        now[0] = 1.
        demo.key(ord("a"))
        self.assertEqual(demo.car.state, "BRAKE_LATCHED")
        for t in (1.05, 1.1, 1.15, 1.2):
            now[0] = t
            demo.observe(observation(t, 0, 115, 40))
        # Explicitly set mock armed for the isolated slowdown transition test.
        demo.car.disarm()
        demo.car.arm()
        now[0] = 1.25
        demo.observe(observation(1.25, 0, 113, 40))
        self.assertEqual(demo.car.speed_percent, 15)
        for t in (1.3, 1.35, 1.4, 1.45):
            now[0] = t
            demo.observe(observation(t, 60, 100, 0))
        self.assertLessEqual(demo.car.speed_percent, 15)

    def test_demo_wires_callbacks_and_stops_on_exit(self):
        from . import collision_demo
        seen = []

        def fake_camera(argv, on_observation, extra_lines, on_key, dashboard_state=None):
            demo = on_observation.__self__
            seen.append(demo)
            on_observation(None)
            self.assertTrue(any("MOCK ONLY" in line for line in extra_lines()))
            on_key(ord("s"))
            return 0

        with patch.object(collision_demo.aruco_webcam, "main", side_effect=fake_camera):
            self.assertEqual(collision_demo.main([
                "--config", "docs/collision_demo.synthetic.json", "--allow-synthetic-config",
                "--calibration", "test-only.json", "--marker-side-cm", "7"]), 0)
        self.assertEqual(seen[0].car.state, "BRAKE_LATCHED")


if __name__ == "__main__":
    unittest.main()

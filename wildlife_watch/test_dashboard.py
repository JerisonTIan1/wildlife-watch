"""UI-only synthetic fixtures; no camera or hardware access."""
import unittest
import numpy as np
from .dashboard import render, current_metrics, RISK_COLORS
from .marker_pose import Observation


class DashboardTests(unittest.TestCase):
    def test_invalid_and_stale_clear_metrics(self):
        valid = Observation(1, True, True, "OK", 50, -2, 10, .1)
        self.assertEqual(current_metrics(valid, 1.01, .075), (50, 10, -2))
        self.assertEqual(current_metrics(valid, 2, .075), (None, None, None))
        self.assertEqual(current_metrics(Observation(1, False, False, "LOST"), 1, .075), (None, None, None))

    def test_feed_aspect_ratio_and_no_input_mutation(self):
        for h, w in ((480, 640), (720, 1280), (640, 480)):
            frame = np.full((h, w, 3), (11, 88, 22), np.uint8)
            before = frame.copy()
            rendered = render(frame, None, {}, 30, 0)
            self.assertEqual(rendered.shape, (800, 1280, 3))
            np.testing.assert_array_equal(frame, before)
            mask = np.all(rendered == (11, 88, 22), axis=2)
            ys, xs = np.where(mask)
            self.assertAlmostEqual((xs.max()-xs.min()+1)/(ys.max()-ys.min()+1), w/h, delta=.003)

    def test_all_risk_states_and_missing_values_render(self):
        for risk in RISK_COLORS:
            result = render(np.zeros((480, 640, 3), np.uint8), None,
                            dict(risk=risk, label="SYNTHETIC geometry/brakes", hardware="USB SERIAL / SIM firmware (no GPIO)",
                                 tracking="TEMPORARILY LOST", policy="STOP", controller="BRAKE_LATCHED", duty=0), 0, 0)
            self.assertTrue(np.any(np.all(result == RISK_COLORS[risk], axis=2)))


if __name__ == "__main__":
    unittest.main()

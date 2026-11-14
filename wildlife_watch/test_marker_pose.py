"""Synthetic intrinsics here are fixtures ONLY, never deployed calibration."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from .marker_pose import Calibration, ClosingSpeed, PoseEstimator, marker_points
from .calibrate_camera import board_points, calibrate_views


class PoseTests(unittest.TestCase):
    def setUp(self):
        self.matrix = np.array([[700., 0, 320], [0, 710., 240], [0, 0, 1]])
        self.distortion = np.array([0.03, -0.01, 0.001, -0.002, 0.0])
        self.calibration = Calibration(self.matrix, self.distortion, (640, 480))

    def corners(self, x=8., z=100.):
        rotation, _ = cv2.Rodrigues(np.array([0.15, 0.2, 0.05]))
        # Face marker's +Y upward, +Z toward camera, with additional tilt.
        rvec, _ = cv2.Rodrigues(rotation @ np.diag([1., -1., -1.]))
        points, _ = cv2.projectPoints(marker_points(7.), rvec, np.array([x, 2., z]), self.matrix, self.distortion)
        return points.reshape(4, 2)

    def test_pose_units_and_sign(self):
        for x, z in [(-8., 40.), (0., 80.), (12., 150.)]:
            observation = PoseEstimator(self.calibration, 7.).observe(self.corners(x, z), (640, 480), 1.)
            self.assertTrue(observation.pose_valid)
            self.assertAlmostEqual(observation.distance_cm, z, places=4)
            self.assertAlmostEqual(observation.lateral_cm, x, places=4)
            self.assertIsNone(observation.closing_speed_cm_s)
            json.dumps(observation.to_dict(), allow_nan=False)

    def test_loss_resets_speed_and_clears_fields(self):
        estimator = PoseEstimator(self.calibration, 7.)
        for t in [0., 0.05, 0.1, 0.15]:
            observation = estimator.observe(self.corners(z=100 - 20*t), (640, 480), t)
        self.assertAlmostEqual(observation.closing_speed_cm_s, 20., places=3)
        lost = estimator.observe(None, (640, 480), 0.2)
        self.assertFalse(lost.detection_valid)
        self.assertFalse(lost.pose_valid)
        self.assertIsNone(lost.distance_cm)
        self.assertIsNone(lost.lateral_cm)
        self.assertIsNone(lost.closing_speed_cm_s)
        recovered = estimator.observe(self.corners(), (640, 480), 0.25)
        self.assertTrue(recovered.pose_valid)
        self.assertIsNone(recovered.closing_speed_cm_s)

    def test_frontal_marker_and_reprojection_rejection(self):
        corners, _ = cv2.projectPoints(marker_points(7.), np.array([np.pi, 0., 0.]),
                                       np.array([0., 0., 100.]), self.matrix, self.distortion)
        estimator = PoseEstimator(self.calibration, 7.)
        observation = estimator.observe(corners.reshape(4, 2), (640, 480), 1.)
        self.assertTrue(observation.pose_valid)
        self.assertAlmostEqual(observation.distance_cm, 100., places=3)
        damaged = self.corners()
        damaged[0] += [20, 10]
        observation = PoseEstimator(self.calibration, 7., .1).observe(damaged, (640, 480), 1.)
        self.assertFalse(observation.pose_valid)

    def test_rejects_mismatch_degenerate_and_duplicate_timestamp(self):
        estimator = PoseEstimator(self.calibration, 7.)
        self.assertEqual(estimator.observe(self.corners(), (1280, 720), 1.).reason, "CALIBRATION_SIZE_MISMATCH")
        self.assertFalse(estimator.observe(np.zeros((4, 2)), (640, 480), 2.).pose_valid)
        self.assertFalse(estimator.observe(self.corners(), (640, 480), 2.).pose_valid)
        self.assertFalse(estimator.observe(np.full((4, 2), np.nan), (640, 480), 3.).pose_valid)

    def test_noisy_speed_and_irregular_timestamps(self):
        speed = ClosingSpeed()
        rng = np.random.default_rng(5)
        times = np.cumsum(rng.uniform(0.025, 0.05, 70))
        distances = 120 - 12 * times + rng.normal(0, 0.15, len(times))
        filtered = [speed.update(float(t), float(z)) for t, z in zip(times, distances)]
        errors = [v - 12 for v in filtered[10:] if v is not None]
        raw_errors = -np.diff(distances) / np.diff(times) - 12
        self.assertLess(np.std(errors), np.std(raw_errors))
        self.assertAlmostEqual(np.mean(filtered[10:]), 12, delta=1)
        self.assertIsNone(speed.update(float(times[-1] + 1), 30))

    def test_receding_and_stationary_speed(self):
        for slope in (0., 10.):
            speed = ClosingSpeed()
            for t in (0., .04, .10, .15):
                result = speed.update(t, 100 + slope*t)
            self.assertAlmostEqual(result, -slope)

    def test_calibration_from_synthetic_checkerboard_views_and_roundtrip(self):
        objects = board_points(9, 6, 2.)
        images = []
        for i in range(18):
            rvec = np.array([-.3 + .12*(i % 5), -.25 + .1*(i % 6), .03*(i % 3)])
            tvec = np.array([-8. + i % 4, -5. + i % 3, 45. + 3*i])
            corners, _ = cv2.projectPoints(objects, rvec, tvec, self.matrix, self.distortion)
            images.append(corners)
        data = calibrate_views([objects]*len(images), images, (640, 480))
        self.assertLess(data["rms_px"], 0.001)
        np.testing.assert_allclose(data["camera_matrix"], self.matrix, atol=.1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calibration.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            loaded = Calibration.load(path)
            self.assertEqual(loaded.image_size, (640, 480))
        with self.assertRaises(ValueError):
            calibrate_views([objects], images[:1], (640, 480))

    def test_webcam_callback_reports_valid_then_lost(self):
        from . import aruco_webcam as app
        from .test_aruco_webcam import marker_frame
        capture = MagicMock()
        capture.read.side_effect = [(True, marker_frame()), (False, None)]
        received = []
        with patch.object(Calibration, "load", return_value=self.calibration), \
             patch.object(app.cv2, "VideoCapture", return_value=capture), \
             patch.object(app.cv2, "namedWindow"), patch.object(app.cv2, "imshow"), \
             patch.object(app.cv2, "destroyAllWindows"), \
             patch.object(app.cv2, "getWindowProperty", return_value=1), \
             patch.object(app.cv2, "waitKey", side_effect=[-1, ord("q")]):
            self.assertEqual(app.main(["--calibration", "fixture.json", "--marker-side-cm", "7"],
                                      on_observation=received.append), 0)
        self.assertEqual(len(received), 2)
        self.assertTrue(received[0].pose_valid)
        self.assertFalse(received[1].pose_valid)
        self.assertIsNone(received[1].distance_cm)
        self.assertGreater(received[1].timestamp_s, received[0].timestamp_s)


if __name__ == "__main__":
    unittest.main()

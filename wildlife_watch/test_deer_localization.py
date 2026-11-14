"""All intrinsics, dimensions and offsets here are synthetic test fixtures."""
from dataclasses import replace
import unittest

import cv2
import numpy as np

from .marker_pose import Calibration, Observation
from .deer_localization import TargetGeometry, DeerLocalizer
from .collision import CollisionConfig, CollisionPredictor


class DeerTests(unittest.TestCase):
    def setUp(self):
        self.calibration = Calibration(np.array([[600., 0, 320], [0, 600., 240], [0, 0, 1]]), np.zeros(5), (640, 480))
        self.geometry = TargetGeometry((0., -10., -5.), (12., 8., 20.))
        self.localizer = DeerLocalizer(self.calibration, self.geometry)

    def marker(self, timestamp=0., rotation=None, z=100.):
        return Observation(timestamp, True, True, "OK", z, 0, 0, .1,
                           marker_rvec=(np.pi, 0., 0.) if rotation is None else rotation,
                           marker_tvec_cm=(0., 0., z))

    def test_offsets_and_projection(self):
        body, box = self.localizer.locate(self.marker(), (640, 480))
        self.assertAlmostEqual(body.distance_cm, 105.)
        self.assertAlmostEqual(body.lateral_cm, 0.)
        self.assertEqual(body.position_reference, "deer_body")
        self.assertAlmostEqual(body.target_half_depth_cm, 10.)
        self.assertAlmostEqual(body.target_half_width_cm, 6.)
        # Frontal pose maps marker -Y to camera +Y. Exact box projection:
        self.assertEqual(box, (282, 271, 358, 329))

    def test_rotation_changes_center_and_collision_extents(self):
        yaw, _ = cv2.Rodrigues(np.array([0., np.pi/2, 0.]))
        rotation, _ = cv2.Rodrigues(yaw @ np.diag([1., -1., -1.]))
        body, _ = self.localizer.locate(self.marker(rotation=tuple(rotation.ravel())), (640, 480))
        self.assertAlmostEqual(body.lateral_cm, 5.)
        self.assertAlmostEqual(body.distance_cm, 100.)
        self.assertAlmostEqual(body.target_half_width_cm, 10.)
        self.assertAlmostEqual(body.target_half_depth_cm, 6.)

    def test_loss_no_box_or_stale_measurements_and_recovery(self):
        for t in (0., .05, .1):
            body, _ = self.localizer.locate(self.marker(t, z=100-10*t), (640, 480))
        self.assertAlmostEqual(body.closing_speed_cm_s, 10.)
        lost, box = self.localizer.locate(Observation(.15, False, False, "LOST"), (640, 480))
        self.assertIsNone(box)
        self.assertFalse(lost.pose_valid)
        self.assertIsNone(lost.distance_cm)
        body, _ = self.localizer.locate(self.marker(.2), (640, 480))
        self.assertIsNone(body.closing_speed_cm_s)

    def test_collision_uses_body_center_and_rotated_extents(self):
        # Marker z=25 is beyond the configured front (10); inferred body extends to 20.
        geometry = TargetGeometry((0., 0., 10.), (4., 4., 20.))
        localizer = DeerLocalizer(self.calibration, geometry)
        body, _ = localizer.locate(self.marker(z=25.), (640, 480))
        predictor = CollisionPredictor(CollisionConfig(10, 10, 5, 1, 1, 0))
        self.assertEqual(predictor.update(body, 0.).risk, "HIGH")
        invalid = replace(body, target_half_depth_cm=None)
        self.assertEqual(CollisionPredictor(predictor.config).update(invalid, 0.).risk, "UNKNOWN")

    def test_reject_invalid_geometry_and_missing_pose(self):
        with self.assertRaises(ValueError):
            TargetGeometry((0, 0, 0), (1, -2, 3))
        body, box = self.localizer.locate(replace(self.marker(), marker_rvec=None), (640, 480))
        self.assertFalse(body.pose_valid)
        self.assertIsNone(box)
        body, box = self.localizer.locate(self.marker(), (1280, 720))
        self.assertFalse(body.pose_valid)

    def test_projection_not_fixed_pixel_shift(self):
        _, near = self.localizer.locate(self.marker(z=100), (640, 480))
        _, far = self.localizer.locate(self.marker(.1, z=200), (640, 480))
        self.assertGreater(near[1]-240, far[1]-240)
        self.assertGreater(near[2]-near[0], far[2]-far[0])


if __name__ == "__main__":
    unittest.main()

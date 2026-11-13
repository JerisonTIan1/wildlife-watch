"""Synthetic perception and mocked capture tests; no physical-camera claims."""

import unittest
from unittest.mock import patch, MagicMock

import cv2
import numpy as np

from . import aruco_webcam as app


def marker_frame(marker_id=0, size=180, x=230, y=150):
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, size)
    frame = np.full((480, 640, 3), 255, dtype=np.uint8)
    frame[y:y + size, x:x + size] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    return frame


class DetectionTests(unittest.TestCase):
    def setUp(self):
        self.detector = app.make_detector()

    def test_id_zero_corners_and_center(self):
        targets, center, status = app.detect_target(marker_frame(), self.detector)
        self.assertEqual(status, "DETECTED")
        self.assertEqual(targets[0].shape, (4, 2))
        np.testing.assert_allclose(center, (319.5, 239.5), atol=1)

    def test_loss_wrong_id_and_reacquisition(self):
        for frame, expected in [(marker_frame(), True),
                                (np.full((480, 640, 3), 255, np.uint8), False),
                                (marker_frame(1), False), (marker_frame(), True)]:
            targets, center, status = app.detect_target(frame, self.detector)
            self.assertEqual(center is not None, expected)
            self.assertEqual(status, "DETECTED" if expected else "NOT DETECTED")

    def test_scale_translation_rotation_and_perspective(self):
        frames = [marker_frame(size=size, x=x, y=80) for size, x in [(36, 30), (80, 480), (260, 160)]]
        original = marker_frame()
        transform = cv2.getRotationMatrix2D((320, 240), 25, 1)
        frames.append(cv2.warpAffine(original, transform, (640, 480), borderValue=(255, 255, 255)))
        source = np.float32([[0, 0], [639, 0], [639, 479], [0, 479]])
        destination = np.float32([[90, 40], [590, 10], [630, 450], [10, 470]])
        frames.append(cv2.warpPerspective(original, cv2.getPerspectiveTransform(source, destination),
                                          (640, 480), borderValue=(255, 255, 255)))
        for frame in frames:
            with self.subTest():
                self.assertEqual(app.detect_target(frame, self.detector)[2], "DETECTED")

    def test_duplicate_target_is_ambiguous(self):
        frame = np.minimum(marker_frame(size=100, x=50), marker_frame(size=100, x=400))
        targets, center, status = app.detect_target(frame, self.detector)
        self.assertEqual(len(targets), 2)
        self.assertIsNone(center)
        self.assertIn("AMBIGUOUS", status)

    def test_annotation_does_not_change_input(self):
        frame = marker_frame()
        before = frame.copy()
        result = app.annotate(frame, *app.detect_target(frame, self.detector), 29.5)
        np.testing.assert_array_equal(frame, before)
        self.assertEqual(result.shape, (584, 640, 3))

    def test_failed_read_clears_center_then_recovers(self):
        capture = MagicMock()
        capture.read.side_effect = [(True, marker_frame()), (False, None), (True, marker_frame())]
        with patch.object(app.cv2, "VideoCapture", return_value=capture), \
             patch.object(app.cv2, "namedWindow"), patch.object(app.cv2, "imshow"), \
             patch.object(app.cv2, "destroyAllWindows"), \
             patch.object(app.cv2, "getWindowProperty", return_value=1), \
             patch.object(app.cv2, "waitKey", side_effect=[-1, -1, ord("q")]), \
             patch.object(app, "annotate", wraps=app.annotate) as draw:
            self.assertEqual(app.main([]), 0)
            self.assertIsNotNone(draw.call_args_list[0].args[2])
            self.assertIsNone(draw.call_args_list[1].args[2])
            self.assertEqual(draw.call_args_list[1].args[3], "CAMERA READ FAILED")
            self.assertIsNotNone(draw.call_args_list[2].args[2])
        capture.release.assert_called_once()

    def test_unavailable_camera_exits_cleanly(self):
        capture = MagicMock()
        capture.isOpened.return_value = False
        with patch.object(app.cv2, "VideoCapture", return_value=capture), \
             patch.object(app.cv2, "destroyAllWindows"):
            self.assertEqual(app.main(["--camera", "9"]), 1)
        capture.release.assert_called_once()


if __name__ == "__main__":
    unittest.main()

"""Calibrated marker-center translation in camera coordinates; no motor logic."""

from collections import deque
from dataclasses import asdict, dataclass
import json
from pathlib import Path

import cv2
import numpy as np


@dataclass
class Calibration:
    matrix: np.ndarray
    distortion: np.ndarray
    image_size: tuple[int, int]

    def __post_init__(self):
        self.matrix = np.asarray(self.matrix, dtype=np.float64)
        self.distortion = np.asarray(self.distortion, dtype=np.float64).reshape(-1)
        if (self.matrix.shape != (3, 3) or not np.isfinite(self.matrix).all()
                or self.matrix[0, 0] <= 0 or self.matrix[1, 1] <= 0
                or not np.allclose(self.matrix[2], [0, 0, 1])
                or self.distortion.size not in (4, 5, 8, 12, 14)
                or not np.isfinite(self.distortion).all()
                or len(self.image_size) != 2
                or any(type(v) is not int or v <= 0 for v in self.image_size)):
            raise ValueError("Invalid calibration matrix, distortion or image size")

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema_version") != 1:
            raise ValueError("Unsupported calibration schema")
        return cls(data["camera_matrix"], data["distortion_coefficients"], tuple(data["image_size"]))


def marker_points(side_cm):
    if not np.isfinite(side_cm) or side_cm <= 0:
        raise ValueError("Marker side must be a positive measured length in cm")
    half = side_cm / 2
    # ArUco canonical TL, TR, BR, BL; marker +Y up, +Z out of its face.
    return np.array([[-half, half, 0], [half, half, 0],
                     [half, -half, 0], [-half, -half, 0]], dtype=np.float64)


@dataclass(frozen=True)
class Observation:
    timestamp_s: float
    detection_valid: bool
    pose_valid: bool
    reason: str
    distance_cm: float | None = None
    lateral_cm: float | None = None
    closing_speed_cm_s: float | None = None
    reprojection_error_px: float | None = None
    marker_id: int = 0
    marker_rvec: tuple[float, float, float] | None = None
    marker_tvec_cm: tuple[float, float, float] | None = None
    target_half_width_cm: float | None = None
    target_half_depth_cm: float | None = None
    position_reference: str = "marker"

    def to_dict(self):
        return asdict(self)


class ClosingSpeed:
    """Least-squares Z slope over <=0.3 seconds; reset on loss or >0.25s gap."""

    def __init__(self):
        self.samples = deque(maxlen=30)

    def reset(self):
        self.samples.clear()

    def update(self, timestamp, distance):
        if self.samples and (timestamp <= self.samples[-1][0] or timestamp - self.samples[-1][0] > 0.25):
            self.reset()
        self.samples.append((timestamp, distance))
        while self.samples and timestamp - self.samples[0][0] > 0.3:
            self.samples.popleft()
        if len(self.samples) < 3 or timestamp - self.samples[0][0] < 0.08:
            return None
        times, distances = np.asarray(self.samples).T
        times = times - times.mean()
        # Positive means approaching (camera-axis Z decreasing).
        return float(-np.dot(times, distances - distances.mean()) / np.dot(times, times))


class PoseEstimator:
    def __init__(self, calibration, marker_side_cm, max_reprojection_px=3.0):
        self.calibration = calibration
        self.points = marker_points(marker_side_cm)
        if not np.isfinite(max_reprojection_px) or max_reprojection_px <= 0:
            raise ValueError("Reprojection threshold must be positive")
        self.max_reprojection_px = max_reprojection_px
        self.speed = ClosingSpeed()
        self.last_timestamp = None

    def observe(self, corners, image_size, timestamp, missing_reason="NOT_DETECTED"):
        """Call once per read; timestamp immediately after read using perf_counter()."""
        if not np.isfinite(timestamp):
            self.speed.reset()
            raise ValueError("Timestamp must be finite")
        detected = corners is not None

        def invalid(reason):
            self.speed.reset()
            return Observation(timestamp, detected, False, reason)

        if self.last_timestamp is not None and timestamp <= self.last_timestamp:
            return invalid("NONMONOTONIC_TIMESTAMP")
        self.last_timestamp = timestamp
        if not detected:
            return invalid(missing_reason)
        if tuple(image_size) != self.calibration.image_size:
            return invalid("CALIBRATION_SIZE_MISMATCH")
        corners = np.asarray(corners, dtype=np.float64)
        if corners.shape != (4, 2) or not np.isfinite(corners).all():
            return invalid("INVALID_CORNERS")
        contour = corners.astype(np.float32)
        if not cv2.isContourConvex(contour) or abs(cv2.contourArea(contour)) < 16:
            return invalid("DEGENERATE_CORNERS")
        try:
            ok, rvec, tvec = cv2.solvePnP(self.points, corners, self.calibration.matrix,
                                        self.calibration.distortion, flags=cv2.SOLVEPNP_ITERATIVE)
            if not ok or not np.isfinite(rvec).all() or not np.isfinite(tvec).all():
                return invalid("PNP_FAILED")
            rotation, _ = cv2.Rodrigues(rvec)
            if np.any((rotation @ self.points.T + tvec)[2] <= 0):
                return invalid("BEHIND_CAMERA")
            projected, _ = cv2.projectPoints(self.points, rvec, tvec,
                                             self.calibration.matrix, self.calibration.distortion)
            error = float(np.sqrt(np.mean(np.sum((projected.reshape(4, 2) - corners) ** 2, axis=1))))
            if error > self.max_reprojection_px:
                return invalid("REPROJECTION_ERROR")
        except cv2.error:
            return invalid("PNP_FAILED")
        x, _, z = tvec.reshape(3)
        speed = self.speed.update(timestamp, float(z))
        return Observation(timestamp, True, True, "OK", float(z), float(x), speed, error,
                           marker_rvec=tuple(float(v) for v in rvec.reshape(3)),
                           marker_tvec_cm=tuple(float(v) for v in tvec.reshape(3)))

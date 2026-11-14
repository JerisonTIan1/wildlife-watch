"""Rigid measured target box in marker coordinates; no visual animal recognition."""
from dataclasses import dataclass, replace
from itertools import product
import json
from pathlib import Path

import cv2
import numpy as np

from .marker_pose import ClosingSpeed, Observation


@dataclass(frozen=True)
class TargetGeometry:
    center_marker_cm: tuple
    size_marker_cm: tuple

    def __post_init__(self):
        for values in (self.center_marker_cm, self.size_marker_cm):
            try:
                valid = len(values) == 3 and np.isfinite(values).all()
            except (TypeError, ValueError):
                valid = False
            if not valid:
                raise ValueError("Geometry requires three finite measured coordinates/dimensions")
        if any(v <= 0 for v in self.size_marker_cm):
            raise ValueError("Target dimensions must be positive")

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema_version") != 1:
            raise ValueError("Unsupported target geometry schema")
        return cls(tuple(data["center_marker_cm"]), tuple(data["size_marker_cm"]))

    def corners(self):
        return np.asarray(self.center_marker_cm) + np.asarray(list(product((-.5, .5), repeat=3))) * self.size_marker_cm


class DeerLocalizer:
    def __init__(self, calibration, geometry):
        self.calibration, self.geometry = calibration, geometry
        self.speed = ClosingSpeed()

    def locate(self, marker: Observation, image_size):
        def invalid(reason):
            self.speed.reset()
            return Observation(marker.timestamp_s, False, False, reason,
                               position_reference="deer_body"), None
        if not marker.pose_valid or not marker.detection_valid:
            return invalid(marker.reason)
        if tuple(image_size) != self.calibration.image_size:
            return invalid("CALIBRATION_SIZE_MISMATCH")
        if marker.marker_rvec is None or marker.marker_tvec_cm is None:
            return invalid("FULL_MARKER_POSE_UNAVAILABLE")
        rvec = np.asarray(marker.marker_rvec, dtype=float)
        tvec = np.asarray(marker.marker_tvec_cm, dtype=float)
        if rvec.shape != (3,) or tvec.shape != (3,) or not np.isfinite([rvec, tvec]).all():
            return invalid("INVALID_MARKER_POSE")
        rotation, _ = cv2.Rodrigues(rvec)
        center = rotation @ np.asarray(self.geometry.center_marker_cm) + tvec
        vertices = self.geometry.corners()
        camera_vertices = vertices @ rotation.T + tvec
        if np.any(camera_vertices[:, 2] <= 0):
            return invalid("TARGET_CROSSES_CAMERA_PLANE")
        projected, _ = cv2.projectPoints(vertices, rvec, tvec, self.calibration.matrix, self.calibration.distortion)
        pixels = projected.reshape(-1, 2)
        if not np.isfinite(pixels).all():
            return invalid("INVALID_TARGET_PROJECTION")
        # Camera-axis enclosing extents, not marker-axis dimensions.
        extents = np.abs(rotation) @ (np.asarray(self.geometry.size_marker_cm) / 2)
        body = replace(marker, distance_cm=float(center[2]), lateral_cm=float(center[0]),
                       closing_speed_cm_s=self.speed.update(marker.timestamp_s, float(center[2])),
                       target_half_width_cm=float(extents[0]), target_half_depth_cm=float(extents[2]),
                       position_reference="deer_body")
        w, h = image_size
        lo, hi = pixels.min(axis=0), pixels.max(axis=0)
        if hi[0] < 0 or hi[1] < 0 or lo[0] >= w or lo[1] >= h:
            return body, None  # inferred body offscreen, not marker loss
        lo = np.maximum(lo, [0, 0])
        hi = np.minimum(hi, [w-1, h-1])
        return body, (*np.floor(lo).astype(int), *np.ceil(hi).astype(int))


def draw_deer(frame, box):
    if box is None:
        return
    x1, y1, x2, y2 = box
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
    # Hershey fonts support ASCII, so use a hyphen instead of an em dash.
    cv2.putText(frame, "DEER - MARKER ASSISTED", (x1, max(18, y1-6)),
                cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 255, 0), 1, cv2.LINE_AA)

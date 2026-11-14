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
    # Draw an em dash as a line: OpenCV Hershey fonts have no Unicode glyph.
    font, scale = cv2.FONT_HERSHEY_SIMPLEX, .5
    left = cv2.getTextSize("DEER", font, scale, 1)[0][0]
    right = cv2.getTextSize("MARKER ASSISTED", font, scale, 1)[0][0]
    width = left + right + 28
    x = max(2, min(x1, frame.shape[1]-width-4))
    y = min(frame.shape[0]-6, max(20, y1-8))
    cv2.rectangle(frame, (x-2, y-17), (min(frame.shape[1]-1, x+width+2), y+5), (22, 28, 22), -1)
    cv2.putText(frame, "DEER", (x, y), font, scale, (0, 255, 0), 1, cv2.LINE_AA)
    cv2.line(frame, (x+left+6, y-5), (x+left+20, y-5), (0, 255, 0), 1, cv2.LINE_AA)
    cv2.putText(frame, "MARKER ASSISTED", (x+left+28, y), font, scale, (0, 255, 0), 1, cv2.LINE_AA)


def draw_geometry_debug(frame, marker, calibration, geometry):
    """Show canonical marker axes and measured box-center direction, not pixel offsets."""
    if not marker.pose_valid or marker.marker_rvec is None or marker.marker_tvec_cm is None:
        return
    points = np.array([[0., 0., 0.], [3., 0., 0.], [0., 3., 0.],
                       geometry.center_marker_cm], dtype=np.float64)
    rvec, tvec = np.asarray(marker.marker_rvec), np.asarray(marker.marker_tvec_cm)
    rotation, _ = cv2.Rodrigues(rvec)
    if np.any((points @ rotation.T + tvec)[:, 2] <= 0):
        return
    pixels, _ = cv2.projectPoints(points, rvec, tvec, calibration.matrix, calibration.distortion)
    pixels = pixels.reshape(-1, 2)
    if not np.isfinite(pixels).all() or np.max(np.abs(pixels)) > 1e6:
        return
    origin, x_axis, y_axis, center = [tuple(np.rint(p).astype(int)) for p in pixels]
    for end, label, color in ((x_axis, "+X marker", (0, 0, 255)),
                              (y_axis, "+Y marker", (255, 200, 0)),
                              (center, "configured body center", (0, 255, 0))):
        cv2.arrowedLine(frame, origin, end, color, 2, tipLength=.15)
        cv2.putText(frame, label, end, cv2.FONT_HERSHEY_SIMPLEX, .4, color, 1, cv2.LINE_AA)

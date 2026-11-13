"""Capture checkerboard views and save measured OpenCV pinhole calibration."""

import argparse
import json
from pathlib import Path
import sys

import cv2
import numpy as np

from .aruco_webcam import configure_camera, finite_number
from .marker_pose import Calibration


def board_points(columns, rows, square_cm):
    if columns < 3 or rows < 3 or not np.isfinite(square_cm) or square_cm <= 0:
        raise ValueError("Need >=3x3 inner corners and a positive measured square size")
    points = np.zeros((columns * rows, 3), np.float32)
    points[:, :2] = np.mgrid[0:columns, 0:rows].T.reshape(-1, 2) * square_cm
    return points


def calibrate_views(object_points, image_points, image_size):
    if len(image_points) < 15 or len(object_points) != len(image_points):
        raise ValueError("Collect at least 15 varied checkerboard views")
    rms, matrix, distortion, rotations, translations = cv2.calibrateCamera(
        object_points, image_points, image_size, None, None)
    Calibration(matrix, distortion, tuple(image_size))
    errors = []
    for objects, corners, rotation, translation in zip(object_points, image_points, rotations, translations):
        projected, _ = cv2.projectPoints(objects, rotation, translation, matrix, distortion)
        errors.append(float(np.sqrt(np.mean(np.sum((projected.reshape(-1, 2) - corners.reshape(-1, 2)) ** 2, axis=1)))))
    if not np.isfinite(rms):
        raise ValueError("Calibration failed: nonfinite RMS")
    return {"schema_version": 1, "camera_matrix": matrix.tolist(),
            "distortion_coefficients": distortion.reshape(-1).tolist(),
            "image_size": list(image_size), "rms_px": float(rms),
            "per_view_rms_px": errors, "views": len(image_points)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--columns", required=True, type=int, help="Inner corners per row, NOT squares")
    parser.add_argument("--rows", required=True, type=int, help="Inner corners per column")
    parser.add_argument("--square-cm", required=True, type=finite_number, help="Measured checkerboard square side")
    parser.add_argument("--output", required=True, type=Path, help="New JSON file (never overwrite)")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--backend", choices=("auto", "dshow", "msmf"), default="auto")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=finite_number, default=30)
    parser.add_argument("--fourcc", choices=("MJPG", "YUY2"))
    parser.add_argument("--autofocus", type=int, choices=(0, 1))
    parser.add_argument("--focus", type=finite_number)
    parser.add_argument("--exposure", type=finite_number)
    parser.add_argument("--auto-exposure", type=finite_number)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("Output already exists; choose a new file")
    if args.camera < 0 or min(args.width, args.height, args.fps) <= 0:
        parser.error("Invalid camera index, dimensions or FPS")
    if args.backend != "auto" and sys.platform != "win32":
        parser.error("dshow/msmf require Windows")
    if args.focus is not None and args.autofocus != 0:
        parser.error("--focus requires --autofocus 0")
    capture = None
    try:
        objects = board_points(args.columns, args.rows, args.square_cm)
        capture = cv2.VideoCapture(args.camera, {"auto": cv2.CAP_ANY, "dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF}[args.backend])
        if not capture.isOpened():
            raise ValueError("Cannot open camera")
        configure_camera(capture, args)
        print("SPACE: accept sharp, varied view; C: calibrate/save >=15 views; Q/Esc: cancel.")
        print("Use the same fixed focus and camera mode as the pose test. No fabricated intrinsics.")
        views = []
        size = None
        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                raise ValueError("Camera read failed; no calibration saved. Restart capture.")
            current_size = (frame.shape[1], frame.shape[0])
            if size is not None and current_size != size:
                raise ValueError("Resolution changed during capture")
            size = current_size
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            found, corners = cv2.findChessboardCorners(gray, (args.columns, args.rows))
            if found:
                corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1),
                                          (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
                cv2.drawChessboardCorners(frame, (args.columns, args.rows), corners, found)
            cv2.putText(frame, f"Views {len(views)} | SPACE save view | C calibrate | Q cancel", (8, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.imshow("WildCross calibration", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27) or cv2.getWindowProperty("WildCross calibration", cv2.WND_PROP_VISIBLE) < 1:
                return 0
            if key == 32 and found:
                if any(np.mean(np.linalg.norm(corners - prior, axis=2)) < 8 for prior in views):
                    print("View too similar; change board position, size or tilt.")
                else:
                    views.append(corners.copy())
                    print(f"Accepted view {len(views)} at {size}")
            if key in (ord("c"), ord("C")):
                if len(views) < 15:
                    print("Need at least 15 varied views.")
                    continue
                data = calibrate_views([objects] * len(views), views, size)
                data.update(square_cm=args.square_cm, inner_corners=[args.columns, args.rows],
                            camera_index=args.camera, backend=capture.getBackendName(), opencv_version=cv2.__version__,
                            focus_readback=capture.get(cv2.CAP_PROP_FOCUS),
                            autofocus_readback=capture.get(cv2.CAP_PROP_AUTOFOCUS))
                serialized = json.dumps(data, indent=2, allow_nan=False)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                with args.output.open("x", encoding="utf-8") as output:
                    output.write(serialized)
                print(f"Saved {args.output}; RMS {data['rms_px']:.3f}px; per-view RMS {data['per_view_rms_px']}")
                print("RMS is fit error, NOT proof of metric accuracy. Validate against a ruler.")
                return 0
    except (ValueError, OSError, cv2.error) as error:
        print(f"Calibration: {error}", file=sys.stderr)
        return 1
    finally:
        if capture is not None:
            capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())

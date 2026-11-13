"""WildCross: live DICT_4X4_50 / ID 0 validation, pixel coordinates only."""

import argparse
from collections import deque
import sys
from time import perf_counter

import cv2
import numpy as np

WINDOW = "WildCross - ArUco webcam test"


def make_detector():
    if not hasattr(cv2, "aruco") or not hasattr(cv2.aruco, "ArucoDetector"):
        raise RuntimeError("OpenCV ArucoDetector missing; install requirements.txt in a clean venv")
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    return cv2.aruco.ArucoDetector(dictionary, parameters)


def detect_target(frame, detector):
    """Return current-frame corners only; never retain a previous detection.

    Multiple ID 0 markers are ambiguous: annotate them but report no single center.
    """
    corners, ids, _ = detector.detectMarkers(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    targets = [] if ids is None else [
        points.reshape(4, 2) for points, marker_id in zip(corners, ids.flatten())
        if marker_id == 0
    ]
    center = tuple(targets[0].mean(axis=0)) if len(targets) == 1 else None
    status = "DETECTED" if len(targets) == 1 else (
        "AMBIGUOUS (multiple ID 0)" if targets else "NOT DETECTED"
    )
    return targets, center, status


def annotate(frame, targets, center, status, fps):
    output = frame.copy()
    for corners in targets:
        pixels = np.rint(corners).astype(np.int32)
        cv2.polylines(output, [pixels], True, (0, 255, 0), 2)
        for index, (x, y) in enumerate(pixels):
            cv2.circle(output, (int(x), int(y)), 5, (0, 220, 255), -1)
            cv2.putText(output, f"C{index}", (int(x) + 6, int(y) - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 255), 1)
        x, y = np.rint(corners.mean(axis=0)).astype(int)
        cv2.drawMarker(output, (int(x), int(y)), (255, 0, 255), cv2.MARKER_CROSS, 18, 2)
        cv2.putText(output, "ID 0", (int(x) + 10, int(y) + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
    # Use a separate header so metadata does not obscure marker corners.
    output = cv2.copyMakeBorder(output, 104, 0, 0, 0, cv2.BORDER_CONSTANT)
    coordinates = "-- (no current center)" if center is None else f"({center[0]:.1f}, {center[1]:.1f}) px"
    lines = [f"DICT_4X4_50 / ID 0: {status}", f"Center: {coordinates}",
             f"FPS (capture + detection): {fps:.1f} | Q / Esc: quit"]
    for index, line in enumerate(lines):
        cv2.putText(output, line, (10, 26 + index * 30), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0, help="Camera index, e.g. 0 or 1")
    parser.add_argument("--backend", choices=("auto", "dshow", "msmf"), default="auto",
                        help="Windows capture backend; try dshow if auto fails")
    args = parser.parse_args(argv)
    if args.camera < 0:
        parser.error("--camera must be nonnegative")
    if args.backend != "auto" and sys.platform != "win32":
        parser.error("dshow/msmf are Windows-only backends")
    capture = None
    try:
        detector = make_detector()
        backend = {"auto": cv2.CAP_ANY, "dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF}[args.backend]
        capture = cv2.VideoCapture(args.camera, backend)
        if not capture.isOpened():
            raise RuntimeError(f"Cannot open camera {args.camera}. Try another index/backend, "
                               "close camera apps, and check Windows camera privacy permissions.")
        print(f"OpenCV {cv2.__version__}; camera {args.camera}; backend {capture.getBackendName()}")
        print("Pixel coordinates only. No distance, ToF, prediction or motor commands. Q/Esc exits.")
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        timestamps = deque(maxlen=30)
        failed_since = None
        previous_status = None
        shape = (480, 640, 3)
        while True:
            ok, frame = capture.read()
            now = perf_counter()
            if not ok or frame is None or frame.size == 0:
                if failed_since is None:
                    failed_since = now
                timestamps.clear()
                # A failed read must not redisplay the previous frame/coordinates.
                frame = np.zeros(shape, dtype=np.uint8)
                targets, center, status, fps = [], None, "CAMERA READ FAILED", 0.0
            else:
                failed_since = None
                shape = frame.shape
                targets, center, status = detect_target(frame, detector)
                timestamps.append(perf_counter())
                elapsed = timestamps[-1] - timestamps[0]
                fps = (len(timestamps) - 1) / elapsed if elapsed > 0 else 0.0
            if status != previous_status:
                print(status)
                previous_status = status
            cv2.imshow(WINDOW, annotate(frame, targets, center, status, fps))
            key = cv2.waitKey(30 if failed_since is not None else 1) & 0xFF
            if key in (ord("q"), ord("Q"), 27) or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                return 0
            if failed_since is not None and now - failed_since >= 3.0:
                raise RuntimeError("Camera reads failed for 3 seconds. Check USB connection and restart.")
    except (RuntimeError, cv2.error) as error:
        print(f"ArUco test: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        if capture is not None:
            capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())

"""WildCross: live DICT_4X4_50 / ID 0 validation, pixel coordinates only."""

import argparse
import math
from collections import deque
import sys
from time import perf_counter

import cv2
import numpy as np

WINDOW = "WildCross - ArUco webcam test"


def make_detector(profile="baseline"):
    if not hasattr(cv2, "aruco") or not hasattr(cv2.aruco, "ArucoDetector"):
        raise RuntimeError("OpenCV ArucoDetector missing; install requirements.txt in a clean venv")
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    if profile == "wide":
        parameters.adaptiveThreshWinSizeMax = 53
        parameters.adaptiveThreshWinSizeStep = 4
    elif profile != "baseline":
        raise ValueError("Unknown detector profile")
    return cv2.aruco.ArucoDetector(dictionary, parameters)


def detect_target(frame, detector, preprocess=None):
    """Return current-frame corners only; never retain a previous detection.

    Multiple ID 0 markers are ambiguous: annotate them but report no single center.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if preprocess is not None:
        gray = preprocess.apply(gray)
    corners, ids, _ = detector.detectMarkers(gray)
    targets = [] if ids is None else [
        points.reshape(4, 2) for points, marker_id in zip(corners, ids.flatten())
        if marker_id == 0
    ]
    center = tuple(targets[0].mean(axis=0)) if len(targets) == 1 else None
    status = "DETECTED" if len(targets) == 1 else (
        "AMBIGUOUS (multiple ID 0)" if targets else "NOT DETECTED"
    )
    return targets, center, status


class DetectionStats:
    """Counts fresh frames; read errors are separate, but extend loss episodes."""

    def __init__(self):
        self.detected = self.lost = self.read_errors = self.missed = 0
        self.seen = False
        self.loss_since = None
        self.last_reacquisition = None

    def update(self, valid, now, read_ok=True):
        if not read_ok:
            self.read_errors += 1
        elif valid:
            self.detected += 1
        else:
            self.lost += 1
        if valid and read_ok:
            if self.loss_since is not None:
                self.last_reacquisition = now - self.loss_since
            self.seen = True
            self.loss_since = None
            self.missed = 0
        else:
            self.missed += 1
            if self.seen and self.loss_since is None:
                self.loss_since = now

    def summary(self, now):
        last = "--" if self.last_reacquisition is None else f"{self.last_reacquisition:.3f}s"
        ongoing = "--" if self.loss_since is None else f"{now - self.loss_since:.3f}s"
        return [f"Detected {self.detected} | Lost {self.lost} | Read errors {self.read_errors}",
                f"Consecutive misses {self.missed} | Loss now {ongoing}",
                f"Last reacquisition: {last} (historical)"]


def request_property(capture, name, prop, value):
    """Readback is diagnostic evidence, never proof that the sensor changed."""
    try:
        accepted = capture.set(prop, value)
        actual = capture.get(prop)
        if not accepted:
            outcome = "UNSUPPORTED/REJECTED"
        elif not math.isfinite(actual) or not math.isclose(actual, value, abs_tol=0.01):
            outcome = "READBACK MISMATCH/UNVERIFIED"
        else:
            outcome = "READBACK MATCH (physical effect unverified)"
        print(f"{name}: requested={value}, readback={actual}: {outcome}")
        return outcome
    except cv2.error as error:
        print(f"{name}: UNSUPPORTED/ERROR: {error}")
        return "UNSUPPORTED/ERROR"


def camera_requests(args):
    # Negotiate format first, then size/rate, then modes before manual values.
    return (
        ("fourcc", cv2.CAP_PROP_FOURCC,
         cv2.VideoWriter_fourcc(*args.fourcc) if args.fourcc else None),
        ("width", cv2.CAP_PROP_FRAME_WIDTH, args.width),
        ("height", cv2.CAP_PROP_FRAME_HEIGHT, args.height),
        ("fps", cv2.CAP_PROP_FPS, args.fps),
        ("auto-exposure (driver units)", cv2.CAP_PROP_AUTO_EXPOSURE, args.auto_exposure),
        ("exposure (driver units)", cv2.CAP_PROP_EXPOSURE, args.exposure),
        ("autofocus", cv2.CAP_PROP_AUTOFOCUS, args.autofocus),
        ("focus (driver units)", cv2.CAP_PROP_FOCUS, args.focus),
    )


def configure_camera(capture, args):
    # No default camera-control mutations.
    for name, prop, value in camera_requests(args):
        if value is not None:
            request_property(capture, name, prop, value)
    print("Driver-reported FPS (not observed):", capture.get(cv2.CAP_PROP_FPS))
    if args.exposure is not None:
        print("Manual exposure requires a driver-supported manual mode; readback alone cannot verify it.")


def format_property(name, value):
    if name == "fourcc" and math.isfinite(value) and value > 0:
        code = int(value)
        label = "".join(chr((code >> (8 * i)) & 255) for i in range(4))
        return f"{value} ({label!r})"
    return str(value)


def report_camera(capture, args, shape=None, fps=None):
    """Query after negotiation and during streaming; unsupported reads stay unknown."""
    print("CAMERA DIAGNOSTICS | backend:", capture.getBackendName())
    for name, prop, requested in camera_requests(args):
        request = "unchanged" if requested is None else format_property(name, requested)
        try:
            value = capture.get(prop)
            observed = format_property(name, value)
            note = ""
            if not math.isfinite(value) or value == 0:
                note = " (support unknown; zero can mean unsupported or a valid setting)"
            elif requested is not None and not math.isclose(value, requested, abs_tol=0.01):
                note = " (MISMATCH)"
            print(f"  {name}: requested={request}; driver-reported={observed}{note}")
        except cv2.error as error:
            print(f"  {name}: requested={request}; unavailable: {error}")
    dimensions = "awaiting frames" if shape is None else f"{shape[1]}x{shape[0]}"
    throughput = "awaiting frames" if fps is None else f"{fps:.1f}"
    print(f"  Actual frame dimensions={dimensions}; observed loop FPS={throughput}")
    print("  Readbacks are driver claims, not proof of sensor exposure or unique frame delivery.")


def finite_number(value):
    number = float(value)
    if not math.isfinite(number):
        raise argparse.ArgumentTypeError("must be finite")
    return number


def annotate(frame, targets, center, status, fps, diagnostics=()):
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
    output = cv2.copyMakeBorder(output, 104 + 30 * len(diagnostics), 0, 0, 0, cv2.BORDER_CONSTANT)
    coordinates = "-- (no current center)" if center is None else f"({center[0]:.1f}, {center[1]:.1f}) px"
    lines = [f"DICT_4X4_50 / ID 0: {status}", f"Center: {coordinates}",
             f"FPS (capture + detection): {fps:.1f} | Q / Esc: quit", *diagnostics]
    for index, line in enumerate(lines):
        cv2.putText(output, line, (10, 26 + index * 30), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return output


def main(argv=None, on_observation=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0, help="Camera index, e.g. 0 or 1")
    parser.add_argument("--backend", choices=("auto", "dshow", "msmf"), default="auto",
                        help="Windows capture backend; try dshow if auto fails")
    parser.add_argument("--width", type=int, help="Requested capture width")
    parser.add_argument("--height", type=int, help="Requested capture height")
    parser.add_argument("--fps", type=finite_number, help="Requested camera FPS, not guaranteed")
    parser.add_argument("--fourcc", choices=("MJPG", "YUY2"), help="Request capture format; omitted leaves driver default")
    parser.add_argument("--diagnostics", action="store_true", help="Report all camera readbacks at startup and every 5 seconds")
    parser.add_argument("--camera-settings", action="store_true", help="Open supported DirectShow driver settings dialog")
    parser.add_argument("--exposure", type=finite_number, help="Raw driver-specific exposure value")
    parser.add_argument("--auto-exposure", type=finite_number, help="Raw driver-specific auto-exposure mode")
    parser.add_argument("--focus", type=finite_number, help="Raw driver-specific manual focus; requires --autofocus 0")
    parser.add_argument("--autofocus", type=int, choices=(0, 1), help="Request autofocus off/on")
    parser.add_argument("--profile", choices=("baseline", "wide"), default="baseline")
    parser.add_argument("--preprocess", choices=("none", "clahe"), default="none")
    parser.add_argument("--calibration", help="Measured calibration JSON; omit for pixel-only mode")
    parser.add_argument("--marker-side-cm", type=finite_number, help="Measured OUTER black-square side in cm")
    args = parser.parse_args(argv)
    if args.camera < 0:
        parser.error("--camera must be nonnegative")
    if bool(args.calibration) != (args.marker_side_cm is not None):
        parser.error("Pose requires both --calibration and --marker-side-cm")
    if args.marker_side_cm is not None and args.marker_side_cm <= 0:
        parser.error("--marker-side-cm must be positive")
    for name in ("width", "height", "fps"):
        if getattr(args, name) is not None and getattr(args, name) <= 0:
            parser.error(f"--{name} must be positive")
    if args.focus is not None and args.autofocus != 0:
        parser.error("--focus requires --autofocus 0 (driver support still must be verified)")
    if args.backend != "auto" and sys.platform != "win32":
        parser.error("dshow/msmf are Windows-only backends")
    if args.camera_settings and (sys.platform != "win32" or args.backend != "dshow"):
        parser.error("--camera-settings requires Windows and --backend dshow")
    capture = None
    stats = DetectionStats()
    try:
        estimator = None
        if args.calibration:
            from .marker_pose import Calibration, PoseEstimator
            estimator = PoseEstimator(Calibration.load(args.calibration), args.marker_side_cm)
        detector = make_detector(args.profile)
        preprocess = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)) if args.preprocess == "clahe" else None
        backend = {"auto": cv2.CAP_ANY, "dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF}[args.backend]
        capture = cv2.VideoCapture(args.camera, backend)
        if not capture.isOpened():
            raise RuntimeError(f"Cannot open camera {args.camera}. Try another index/backend, "
                               "close camera apps, and check Windows camera privacy permissions.")
        print(f"OpenCV {cv2.__version__}; camera {args.camera}; backend {capture.getBackendName()}")
        configure_camera(capture, args)
        if args.camera_settings:
            try:
                if not capture.set(cv2.CAP_PROP_SETTINGS, 1):
                    print("Driver settings dialog unsupported/rejected.")
            except cv2.error as error:
                print(f"Driver settings dialog unavailable: {error}")
        if args.diagnostics:
            report_camera(capture, args)
        print(f"Detector profile={args.profile}; preprocessing={args.preprocess}")
        print("Calibrated pose enabled." if estimator else "Pixel coordinates only (no calibration supplied).")
        print("No ToF, prediction or motor commands. Q/Esc exits.")
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        timestamps = deque(maxlen=30)
        failed_since = None
        previous_status = None
        shape = (480, 640, 3)
        actual_shape = None
        last_report = float("-inf")
        last_camera_report = float("-inf")
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
                if shape != actual_shape:
                    print(f"Actual frames: {shape[1]}x{shape[0]}; backend {capture.getBackendName()}")
                    actual_shape = shape
                targets, center, status = detect_target(frame, detector, preprocess)
                timestamps.append(perf_counter())
                elapsed = timestamps[-1] - timestamps[0]
                fps = (len(timestamps) - 1) / elapsed if elapsed > 0 else 0.0
            if status != previous_status:
                print(status)
                previous_status = status
            observed_at = perf_counter()
            if args.diagnostics and observed_at - last_camera_report >= 5:
                report_camera(capture, args, actual_shape, fps)
                last_camera_report = observed_at
            stats.update(center is not None, observed_at, read_ok=failed_since is None)
            dimensions = "awaiting frame" if actual_shape is None else f"{actual_shape[1]}x{actual_shape[0]}"
            diagnostics = [f"Actual {dimensions} | Backend {capture.getBackendName()}", *stats.summary(observed_at)]
            if estimator is not None:
                observation = estimator.observe(targets[0] if center is not None else None,
                                                (shape[1], shape[0]), now, status)
                if observation.pose_valid:
                    speed_text = "-- warming up" if observation.closing_speed_cm_s is None else f"{observation.closing_speed_cm_s:.1f} cm/s"
                    diagnostics.extend([f"Forward Z: {observation.distance_cm:.1f} cm | Right X: {observation.lateral_cm:.1f} cm",
                                        f"Closing speed: {speed_text}"])
                else:
                    diagnostics.extend([f"Pose INVALID: {observation.reason}", "Distance / lateral / speed: --"])
                if on_observation is not None:
                    on_observation(observation)
            if observed_at - last_report >= 1:
                print(f"Observed FPS {fps:.1f} | " + " | ".join(diagnostics))
                last_report = observed_at
            cv2.imshow(WINDOW, annotate(frame, targets, center, status, fps, diagnostics))
            key = cv2.waitKey(30 if failed_since is not None else 1) & 0xFF
            if key in (ord("q"), ord("Q"), 27) or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                return 0
            if failed_since is not None and now - failed_since >= 3.0:
                raise RuntimeError("Camera reads failed for 3 seconds. Check USB connection and restart.")
    except (RuntimeError, ValueError, KeyError, OSError, cv2.error) as error:
        print(f"ArUco test: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        print("Final: " + " | ".join(stats.summary(perf_counter())))
        if capture is not None:
            capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())

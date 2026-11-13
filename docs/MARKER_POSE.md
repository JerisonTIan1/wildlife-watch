# Calibrated marker distance and relative closing speed

The existing webcam test can now estimate ID 0's translation using measured
intrinsics, distortion and marker size. Without `--calibration`, it remains
pixel-only. No deployment intrinsics or default 70 mm marker size are supplied.
Calibration and marker size must both be measured before claiming accuracy.

## 1. Prepare and calibrate

Print a flat checkerboard at actual size, mount it rigidly and measure several
squares with a ruler. Use the mean **square side in centimeters**. Columns/rows
are **inner corner counts**, not square counts: a 10x7-square board has 9x6 inner
corners. Check that horizontal and vertical print scale agree.

Use the same Logitech camera, resolution, optical zoom/crop and focus as the
pose run. Prefer verified fixed focus; autofocus changes can invalidate intrinsics.
The utility supports the same exposure/focus/FPS/format requests as the webcam
test. `--autofocus 0` alone does not choose a good focus: establish a sharp focus
setting first and verify driver support. No property request is assumed honored.

Example below is **only for a physically measured 2.00 cm-square, 9x6-inner-corner
board**; replace values and camera index with yours:

```powershell
.\.venv\Scripts\python.exe -m wildlife_watch.calibrate_camera --camera 1 --backend dshow --width 640 --height 480 --fps 30 --fourcc MJPG --columns 9 --rows 6 --square-cm 2.00 --output runs/logitech-calibration.json
```

Use the format that worked on your camera. Hold the complete board still and sharp,
then press **Space** to accept a view. Collect at least 15, preferably 20–30,
with diverse tilt, distance, and positions across the center, edges and corners
of the image. Avoid all-front-on views. Nearly identical corner locations are
rejected, but that simple check does not guarantee a well-conditioned calibration.
Press **C** to calibrate/save or **Q/Escape** to cancel. The tool does not overwrite
existing calibration files. A camera-read failure cancels without saving.

JSON stores camera matrix, distortion coefficients, actual image size, global and
per-view reprojection RMS in pixels, board dimensions, view count, backend and
focus readbacks. Inspect large per-view errors; recollect sharp, varied images if
needed. Low fitting error alone does not prove accurate distance. Raw calibration
images are not saved by this minimal utility. Generated files under `runs/` are
ignored by Git.

## 2. Measure the marker and run pose

Measure the **outer black square**, including its black border, excluding the
white cardboard margin. Verify it is square and flat. Do not substitute the
approximately 70 mm description for a measurement: size error scales distance.
If its measured side is exactly 70.0 mm, that is `7.00` cm:

```powershell
.\.venv\Scripts\python.exe -m wildlife_watch.aruco_webcam --camera 1 --backend dshow --width 640 --height 480 --fps 30 --fourcc MJPG --calibration runs/logitech-calibration.json --marker-side-cm 7.00
```

Use your measured value and matching camera settings. Missing/malformed calibration
fails clearly. A frame-size mismatch invalidates pose; intrinsics are not silently
scaled. Same-sized frames from a different camera/crop/focus are NOT automatically
detectable, so matching camera setup is your responsibility.

## Coordinates, quality and timing

- Origin: camera optical center. **+X right, +Y down, +Z forward** in the image's
  camera frame. Units are centimeters. Lateral offset is signed X.
- `distance_cm` is Z to the **marker center**, not Euclidean range, bumper distance,
  deer front surface distance or ToF range. A pitched/yawed moving camera changes
  these axes; this is not a world-frame or vehicle-frame estimate.
- `solvePnP(..., SOLVEPNP_ITERATIVE)` uses the four canonical ArUco corners with
  measured square object points, intrinsics and distortion. It rejects degenerate
  corners, nonfinite results, points behind the camera, and reprojection RMS over
  3 px. That threshold is an initial diagnostic gate, not a confidence certificate.
  Four coplanar points remain sensitive to blur, small image size, tilt and planar
  pose ambiguity. No orientation or uncertainty guarantee is made.
- `timestamp_s` uses `time.perf_counter()` immediately after `capture.read()`.
  It is monotonic host receipt time, **not** UTC or sensor exposure time. Camera
  buffering, exposure and repeated frames can bias speed; FPS is never used as dt.
- Positive closing speed means decreasing Z; negative means receding. This is
  relative camera-axis motion and can include camera rotation, not just trolley speed.
- Speed is the negative least-squares Z slope over up to 0.3 seconds / 30 valid
  samples. It needs >=3 samples spanning >=0.08 s. This smooths derivatives and
  introduces lag during acceleration; distance/lateral remain current-frame PnP.
- Loss, ambiguous ID, failed read or rejected pose clears every measurement and
  resets speed history. Reacquisition reports pose immediately but speed stays
  `None` during warmup. A gap >0.25 s also resets speed. Non-increasing timestamps
  invalidate that observation; no differentiation across the gap is performed.

## Prediction-team interface

`wildlife_watch.marker_pose.Observation` is a frozen dataclass with `to_dict()`:

```python
{
    "timestamp_s": 123.45,       # example only, monotonic host time
    "detection_valid": True,    # exactly one ID 0 detected this frame
    "pose_valid": True,         # geometry/calibration checks passed
    "reason": "OK",
    "distance_cm": 100.0,       # example only
    "lateral_cm": -5.0,
    "closing_speed_cm_s": None, # unavailable during warmup/loss
    "reprojection_error_px": 0.2,
    "marker_id": 0
}
```

For a direct integration, call `PoseEstimator(calibration, measured_side_cm)` once,
then `.observe(corners_or_none, (width, height), receipt_timestamp)` on each frame.
Pass `None` for loss, duplicate target IDs and read failures. Do not skip invalid
frames. Consumers must check `pose_valid`, `closing_speed_cm_s is not None` and
freshness independently; detection validity alone does not establish valid pose.
These numerical gates do not establish real-world accuracy.

The existing webcam entry point also accepts a synchronous callback:

```python
from wildlife_watch.aruco_webcam import main

def consume(observation):
    record = observation.to_dict()
    # Pass to your integration layer; do not block capture here.
    print(record)

main(["--camera", "1", "--backend", "dshow",
      "--calibration", "runs/logitech-calibration.json",
      "--marker-side-cm", "7.00"], on_observation=consume)
```

Again replace marker size with your measured value and match capture settings.
Callbacks occur per attempted read only when pose mode is enabled. No background
publisher runs after exit; consumers must enforce a freshness timeout if the
camera blocks or the process stops. There is no motor, serial or ToF integration.

## 3. Validate measured distance before speed

1. With the camera fixed, place the marker near the optical axis at several
   independently measured depths across the intended operating range. Record
   ruler distance, reported Z, signed error and stationary variation. Account for
   the optical-center reference; measuring from the bumper gives an offset.
2. At fixed Z, move it left/right by measured amounts; confirm X sign/scale.
   Repeat at image edges and representative tilts. Do not claim a usable range
   from calibration RMS alone.
3. Hold stationary: closing speed should fluctuate around zero. Move toward and
   away at a measured pace; confirm signs and compare against distance/time.
4. Cover the marker, create blur, and restore it. All fields must clear during
   loss; speed must warm up again. Repeat with the camera on the moving car.

Report calibration RMS/per-view errors, measured square/marker sizes, focus/mode,
distance error table, stationary jitter, speed comparison, and loss/recovery
behavior. No physical calibration or metric-distance validation has been performed
by the agent; these remain required user measurements.

```powershell
.\.venv\Scripts\python.exe -m unittest wildlife_watch.test_marker_pose wildlife_watch.test_aruco_webcam -v
```

Synthetic tests use explicitly artificial intrinsics only as fixtures: known
projected poses with distortion, frontal/tilted geometry, lateral signs, calibration
recovery, rejection gates, irregular timestamps, approach/recede/stationary speed,
noise reduction, and loss resets. They do not validate the physical Logitech camera.
Verification: all 21 combined pose/webcam tests passed on Python 3.13/OpenCV
4.14.0, including callback invalidation on read failure. Python compilation and
calibration CLI help also passed.

References: [OpenCV PnP](https://docs.opencv.org/doc/doxygen/html/d5/d1f/calib3d_solvePnP.html),
[OpenCV calibration API](https://docs.opencv.org/4.8.0/d9/d0c/group__calib3d.html).

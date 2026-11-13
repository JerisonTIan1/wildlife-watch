# WildCross ArUco webcam validation

This standalone test uses the existing `wildlife_watch` package. It detects
`DICT_4X4_50`, ID **0** with OpenCV's `ArucoDetector`. It performs no deer
recognition, distance estimation, ToF reading, prediction or motor control.
Your approximately 70 mm black square is a physical test fixture; its size is
not used to infer distance. Camera calibration is not needed for this pixel-only test.

## Install and run on Windows PowerShell

From the repository root, with Python 3.11+ (3.13 used for verification):

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m wildlife_watch.aruco_webcam --camera 0
```

If `.venv` already exists, reuse it and skip creation. No activation or PowerShell
execution-policy change is required. The existing `opencv-python>=4.8,<5`
dependency supplies the API; use a clean environment and do not mix OpenCV wheel
variants (`opencv-python`, contrib, or headless) in it. The GUI requires a
non-headless wheel.

Select another camera or Windows backend if necessary:

```powershell
.\.venv\Scripts\python.exe -m wildlife_watch.aruco_webcam --camera 1
.\.venv\Scripts\python.exe -m wildlife_watch.aruco_webcam --camera 1 --backend dshow
.\.venv\Scripts\python.exe -m wildlife_watch.aruco_webcam --camera 1 --backend msmf
```

Camera indices are machine-dependent; confirm the feed is the Logitech camera,
not the laptop camera. Close Teams/Zoom/Camera and other camera users. Check
Windows Settings > Privacy & security > Camera > desktop app access. The terminal
prints OpenCV version, selected backend, and detection-state transitions.
Press **Q**, **Escape**, or close the window to exit; Ctrl+C also releases capture.

## Expected display

- Green marker outline, four yellow corners C0..C3, magenta center and ID 0.
- `DETECTED` and center `(x, y)` in pixels from the original camera image's
  top-left; x increases rightward and y downward. The center is the mean of the
  four detected corners. The separate display header does not shift reported coordinates.
- Rolling FPS across up to 30 successfully processed frames, including capture,
  detection and loop overhead. This is observed processing throughput, not the
  camera's advertised FPS or a latency measurement. Initially FPS is 0 until
  two frames arrive; it resets after a failed read.
- `NOT DETECTED` and `-- (no current center)` immediately when ID 0 is absent.
  Other IDs do not count. Multiple ID 0 markers produce `AMBIGUOUS` with no single center.
- Failed reads show a blank `CAMERA READ FAILED` frame, never the old image or
  coordinates. Reads are retried; persistent failure for 3 seconds exits with an
  error. This limit is checked between reads; it cannot interrupt a blocked camera driver.

## Physical validation and what to report

Keep the full black border visible with white margin around it on the backing.
Start stationary and front-on in good light, then move closer, farther, left and
right. Test the intended demo lighting, sideways motion and moderate trolley
rotation. Cover/remove the marker briefly, then restore it: coordinates must
disappear during loss and return on reacquisition. Avoid interpreting synthetic
success as evidence of motion-blur tolerance or real-world range.

Report:

1. Webcam model, camera index/backend, OpenCV version and lighting conditions.
2. Typical FPS stationary and moving; any freezes or camera read errors.
3. Closest/farthest **manually measured** distances with stable ID 0 detection.
4. Whether sideways motion/tilt causes flicker, and roughly how fast you moved it.
5. Whether loss clears coordinates immediately and reacquisition works.
6. A screenshot or short recording of success and the worst failure condition.

If detection fails, first confirm the dictionary/ID and complete black border,
check focus/glare and use a larger apparent marker (move closer). The 70 mm size
alone does not guarantee a detection range. Do not add distance/braking logic
until this physical test is reliable under the intended demo conditions.

## Automated checks (no webcam)

```powershell
.\.venv\Scripts\python.exe -m unittest wildlife_watch.test_aruco_webcam -v
.\.venv\Scripts\python.exe -m wildlife_watch.aruco_webcam --help
```

Tests use generated markers for ID filtering, pixel coordinates, scaling,
translation, rotation, perspective, loss/reacquisition and duplicate IDs, plus
mocked camera failures/cleanup. These are not a physical Logitech validation.

Verified locally: all seven tests passed on Windows with Python 3.13 and OpenCV
4.14.0; module compilation, this CLI's help and the existing preview CLI's help
also passed. The physical webcam and printed marker have not yet been tested.

API reference: [OpenCV ArUco detection tutorial](https://docs.opencv.org/4.12.0/d5/dae/tutorial_aruco_detection.html).

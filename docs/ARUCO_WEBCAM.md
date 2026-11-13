# WildCross ArUco webcam validation

**Next stage:** [camera calibration, marker pose and closing-speed testing](MARKER_POSE.md).
Physical detection is now reported working at approximately 30 FPS at 640x480,
with loss during significant motion. The blur investigation below is historical
context. Pixel-only operation remains the default; calibrated pose is opt-in.

## Motion-blur investigation: start here

Latest physical observations: DirectShow, actual 640x480, approximately 15 FPS,
severe blur while the camera moves, reliable ID 0 detection when sharp. The
detector has not been changed for this capture-settings update. No sharpening,
interpolation, smoothing or position prediction was added.

Existing CLI controls are `--width`, `--height`, `--fps`, `--exposure`,
`--auto-exposure`, `--focus` and `--autofocus`. New controls:

- `--diagnostics`: prints requested versus driver-reported width, height, FPS,
  FOURCC, exposure, auto-exposure, focus and autofocus at startup and every five
  seconds while streaming. Also reports actual array dimensions, observed loop
  FPS and backend. Zero/unsupported readbacks are explicitly ambiguous.
- `--fourcc MJPG`: requests MJPEG with `CAP_PROP_FOURCC` before resolution/FPS
  negotiation. `--fourcc YUY2` is available for an explicit comparison if supported.
  Omission leaves format selection to the driver. Readback is checked again
  during capture because subsequent negotiation may alter earlier requests.
- `--camera-settings`: opens the driver settings dialog when supported; requires
  Windows and `--backend dshow`. CLI requests are applied **before** the dialog;
  dialog changes can override them. Close the dialog to start the video test.

### Three physical candidates

Use your working index instead of `1`. Keep baseline detection and no preprocessing.
Run A and B under identical lighting, focus/exposure settings and camera movement.
Let capture settle for five seconds, then compare at least 30 seconds each.

**A — current/default format, explicit 640x480 and requested 30 FPS:**

```powershell
.\.venv\Scripts\python.exe -m wildlife_watch.aruco_webcam --camera 1 --backend dshow --width 640 --height 480 --fps 30 --diagnostics
```

**B — same settings, request MJPEG:**

```powershell
.\.venv\Scripts\python.exe -m wildlife_watch.aruco_webcam --camera 1 --backend dshow --width 640 --height 480 --fps 30 --fourcc MJPG --diagnostics
```

Compare observed FPS, actual dimensions and reported FOURCC. If A already
reports MJPG, B is not a distinct-format comparison. If appropriate, rerun A with
`--fourcc YUY2`, verifying support. Restarting without `--fourcc` does not promise
restoration of the old format: drivers can retain settings. An MJPG readback is
driver confirmation only; rejected/unknown/mismatched results are not success.

**C — supported format from A/B, shorter manual exposure with more light:**

```powershell
.\.venv\Scripts\python.exe -m wildlife_watch.aruco_webcam --camera 1 --backend dshow --width 640 --height 480 --fps 30 --fourcc MJPG --diagnostics --camera-settings
```

Use MJPG here only if B confirmed support; otherwise omit/change it. In the driver
dialog, note the original settings, disable automatic exposure if offered, and
move exposure one supported step toward a shorter duration. Close the dialog,
inspect the periodic readbacks, and repeat the same camera motion. Add illumination
if the image becomes too dark. Repeat one step at a time until motion sharpness
improves without losing readable marker contrast. Restore original settings if
needed; this tool does not restore them automatically.

Windows documents a log2-seconds convention for camera exposure: **if your driver
uses that convention**, -5 is 1/32 s, -6 is 1/64 s, and -7 is 1/128 s. These are
examples, not verified Logitech settings or universally accepted OpenCV values.
The supported range is device-specific. [Microsoft exposure property reference](https://learn.microsoft.com/windows-hardware/drivers/stream/ksproperty-cameracontrol-exposure).

Once the dialog/readbacks establish valid values, repeat using `--exposure VALUE`
and, only if its encoding has been verified, `--auto-exposure VALUE`. Do not copy
0/1 or 0.25/0.75 mode values from another backend and assume manual mode engaged.
`--autofocus 0 --focus VALUE` is already supported for a separate focus experiment;
first verify the driver accepts both. Keep focus unchanged while comparing
exposure, and retest near/far distances if locking focus.

**Interpretation:** approximately 15 FPS is not a measurement of exposure time.
MJPEG may change transport throughput but does not itself remove exposure blur.
We have not yet measured an FPS or sharpness improvement from these candidates.
Loop FPS includes detection/display overhead and cannot prove the camera delivered
unique sensor frames. Use visible moving-edge sharpness and detection loss counts
as physical evidence, alongside driver readbacks. Property behavior depends on
hardware, driver and backend. [OpenCV video I/O properties](https://docs.opencv.org/4.12.0/d4/d15/group__videoio__flags__base.html).

For each candidate, report: reported FOURCC and exposure modes/values, actual
dimensions, observed FPS range, stationary/moving detection counts, consecutive
misses, lighting, and whether moving edges are visibly sharper. Use A/B/A order
and the same motion to reduce misleading comparisons.

Capture update verification: all 13 automated tests passed on Python 3.13/OpenCV
4.14.0, including existing detector tests, format request ordering, unchanged
default controls, unknown readbacks and diagnostic error handling. CLI help
passed. No physical camera settings or format benchmark was performed by the agent.

This standalone test uses the existing `wildlife_watch` package. It detects
`DICT_4X4_50`, ID **0** with OpenCV's `ArucoDetector`. It performs no deer
recognition, ToF reading, prediction or motor control. Without calibration it
does not estimate distance; calibrated pose is documented in the link above.
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

Initial verification: seven tests passed on Windows with Python 3.13 and OpenCV
4.14.0. The user subsequently validated the physical Logitech webcam and printed
marker: stationary detection works, motion/hand-held detection is intermittent,
and observed throughput fluctuates around 15–30 FPS. The new controls and
experimental detector options below have not yet been physically validated.

## Reliability diagnostics and camera controls

Start with the unchanged baseline detector and explicit capture requests:

```powershell
.\.venv\Scripts\python.exe -m wildlife_watch.aruco_webcam --camera 1 --backend dshow --width 640 --height 480 --fps 30
```

Use the camera index that worked previously. Width, height and FPS are requests,
not promises. Startup prints each request, setter result/readback classification,
driver-reported FPS and backend. Actual dimensions come from received frames,
not camera properties; they appear in the webcam overlay and terminal. Observed
processing FPS remains a rolling throughput measurement, not exposure duration.
Try 1280x720 as a separate experiment if supported; more marker pixels may help
at range but higher resolution may reduce throughput. Compare actual dimensions.

Optional controls leave camera settings alone unless supplied:

| Argument | Meaning |
| --- | --- |
| `--autofocus 0` / `--autofocus 1` | Request autofocus off/on |
| `--focus VALUE` | Raw driver focus value; requires `--autofocus 0` |
| `--exposure VALUE` | Raw driver exposure value, not seconds |
| `--auto-exposure VALUE` | Raw driver-specific auto/manual exposure mode |

No universal exposure range, focus range or auto-exposure mode encoding is
assumed for the unknown Logitech model. Obtain valid values from that camera's
driver controls/documentation. Manual exposure may be ineffective while auto
exposure remains enabled. Autofocus-off rejection also means manual focus is
unverified. Unsupported/rejected setters and mismatched readbacks are printed;
a matching readback **does not prove** the sensor honored the setting. Drivers
can echo values, return zero for unsupported reads, quantize settings, or change
them later. Verify the visible focus/exposure effect; settings may persist after
exit and are not automatically restored. If controls fail under one backend,
compare `auto`, `dshow` and `msmf` without assuming all support the same features.

Counters appear in the webcam overlay, once-per-second terminal summaries and
the final summary:

- **Detected / Lost:** successfully received frames with exactly one ID 0 /
  without a unique ID 0 (including ambiguity). Detection rate is detected divided
  by detected + lost. Read errors are excluded and counted separately.
- **Consecutive misses:** unsuccessful observations since the last detection,
  including failed reads. These are read attempts, not an estimate of frames
  dropped inside the camera or driver.
- **Loss now:** elapsed time since the first missed observation after a previous
  detection. Initial acquisition is not reacquisition.
- **Last reacq:** elapsed time from that first missed observation to the next
  unique ID 0 detection. It is explicitly historical, not a current position.
  This measures an observed loss episode, not latency since the target physically
  re-entered view. Covering/removing the marker contributes to the duration.

No smoothing, predicted centers, stale coordinates or relaxed ID correction
were added. A missing/ambiguous observation stays invalid.

## Controlled detector comparison

Default `--profile baseline --preprocess none` is the previous detector:
OpenCV defaults plus subpixel corner refinement. Optional `--profile wide`
uses adaptive threshold windows 3..53 in steps of 4 (previously default 3..23
in steps of 10). Optional `--preprocess clahe` applies CLAHE to grayscale with
clip limit 2 and an 8x8 tile grid. Neither changes dictionary, target ID or
error-correction tolerance. These are experiments, not proven fixes for blur.

```powershell
.\.venv\Scripts\python.exe -m wildlife_watch.benchmark_aruco
.\.venv\Scripts\python.exe -m unittest wildlife_watch.test_aruco_webcam -v
```

Local synthetic benchmark: OpenCV 4.14.0, 40 generated 640x480 frames,
single-threaded detection, warmup plus three passes. All four configurations
(baseline, wide, baseline+CLAHE, wide+CLAHE) had identical results:

| Condition | Unique frames detected / tested, per pass |
| --- | --- |
| Clean | 3 / 3 |
| Horizontal motion blur | 6 / 12 |
| Low contrast | 6 / 9 |
| Defocus | 6 / 9 |
| Partially occluded marker | 0 / 3 |
| Blank / other marker IDs | 0 false positives / 4 |

Median motion-blur processing times were 1.58 ms baseline, 5.83 ms wide,
2.33 ms baseline+CLAHE and 7.07 ms wide+CLAHE. These exclude capture, display
and logging; timings vary by machine/run. Repeated frames are not independent
trials. The small negative set does not establish a general false-positive rate.
**No detection improvement was demonstrated**, so defaults were retained.
Eleven tests passed, including control rejection/mismatch handling, argument
validation, counter/reacquisition semantics and invalid observations in all profiles.

## Next physical test: isolate one cause at a time

1. Mount the marker flat on the trolley with its entire black border and white
   margin exposed. Compare this against holding it by the backing edges. Fingers,
   bending, tilt, and hand motion are competing explanations; do not assume the
   detector is the cause.
2. Run the baseline for a fixed 30-second stationary interval, then a separate
   30-second repeatable sideways-motion interval at a measured distance. Restart
   between runs to reset counters. Record actual resolution/backend, FPS range,
   detected/lost/errors, longest observed miss streak and reacquisition times.
3. Improve illumination and repeat unchanged camera settings. If possible,
   compare a supported shorter exposure with sufficient light. Higher requested
   FPS alone does not establish shorter exposure or less blur.
4. Check whether focus visibly hunts. Compare supported fixed focus at the test
   distance against autofocus; then repeat near/far tests. Fixed focus is not
   automatically better across the whole operating range.
5. Only then compare resolution or one detector option at a time, alternating
   baseline/variant/baseline with the same lighting, distance and motion. Live
   trials are not identical-input benchmarks; report that limitation.

Physical improvements from lighting, exposure, focus, resolution or either
detector option remain unverified. Reliable stationary detection alone does not
validate a front-facing camera on a moving car. Repeat the winning settings with
the camera moving and the actual mount before integrating collision logic.

Control semantics: [OpenCV video I/O properties](https://docs.opencv.org/doc/doxygen/html/d4/d15/group__videoio__flags__base.html).
Detector semantics: [OpenCV DetectorParameters](https://docs.opencv.org/4.12.0/d1/dcd/structcv_1_1aruco_1_1DetectorParameters.html).

API reference: [OpenCV ArUco detection tutorial](https://docs.opencv.org/4.12.0/d5/dae/tutorial_aruco_detection.html).

# Oh Deer!

**Predicting wildlife collisions before they happen.**

Wildlife can enter a vehicle's path with little warning. Oh Deer! explores how camera-based relative motion estimates can identify a potential collision and request reduced motor output on a miniature vehicle before contact.

This hackathon prototype uses a **marker-equipped simulated reindeer**, not a trained wildlife classifier. The repository retains its original name, `wildlife-watch`, and its Python package remains `wildlife_watch`.

<img width="959" height="566" alt="image" src="https://github.com/user-attachments/assets/6dfc6009-fc29-4aea-9dc3-3d723f9f64cd" />

<img width="2160" height="2880" alt="image" src="https://github.com/user-attachments/assets/42a8c5b1-39fc-4c4c-845d-9425b44b9101" />

<img width="2160" height="2880" alt="image" src="https://github.com/user-attachments/assets/00f96594-2d39-496b-9a29-b7c69512dd90" />




## What we built

- Live Logitech webcam detection of ArUco `DICT_4X4_50`, ID `0`.
- Camera calibration and calibrated PnP pose estimation: forward distance, lateral offset and timestamp-based relative closing speed.
- Marker-assisted deer localization: full marker rotation and translation project a configured 3D body box onto the image.
- A straight-driving, constant-relative-velocity collision predictor reporting LOW, MEDIUM, HIGH or UNKNOWN risk and predicted time to conflict.
- An OpenCV dashboard, mock controller, explicit arming, latched stops and independent host freshness monitoring.
- A dedicated USB ASCII transport for the STM32 NUCLEO-G431KB motor controller.

**What has actually worked:** physical Python-to-STM32 motor commands, and an integrated live webcam-to-motor demonstration with the driven wheels raised. The integrated demonstration actuated the motors, then latched STOP when marker detection was lost. Reacquisition does not automatically restart the motors. **Autonomous ground-driving collision avoidance has not been validated.**

## How it works

```text
Webcam -> OpenCV/ArUco -> Pose Estimation -> Collision Predictor
       -> PWM Decision -> USB Serial -> STM32 NUCLEO-G431KB
       -> TB6612FNG -> DC Motors
```

PnP uses measured camera intrinsics, distortion and marker side length. Marker-to-body offsets locate the configured deer body relative to the camera. Successive valid observations estimate relative motion; the predictor checks whether the target will overlap a configured vehicle corridor within a short horizon. Missing observations remain UNKNOWN, never fabricated current positions.

The mock demo applies the existing braking policy. The separate wheels-raised output demonstration maps LOW to PWM 255, MEDIUM to 200, and HIGH/UNKNOWN/loss/stale input to latched STOP. These duties are **not measured vehicle speeds**. Normal physical-backend operation remains gated on measured geometry and stopping bounds.

## Technologies and hardware

Python, OpenCV (`cv2.aruco`, calibration, `solvePnP`, projection), NumPy, pyserial, Windows DirectShow, a Logitech USB webcam, printed ArUco marker, 3D-printed reindeer/vehicle components, STM32 NUCLEO-G431KB, TB6612FNG and DC motors.

The tested serial connection is ST-LINK virtual COM at **115200 baud**, currently COM8 on the demo laptop. Firmware accepts newline-delimited PWM integers or `STOP`, with `PWM = n` / `STOPPED` acknowledgments. STOP disables outputs and **coasts**, rather than guaranteeing active braking. Firmware timeout is **2000 ms**.

The Arduino V1/SIM code in [firmware](firmware/README.md) is an earlier, separate dry-run implementation. It is incompatible with the working STM32 ASCII protocol; do not use its V1 transport for this demo. ToF integration is future work, not part of the demonstrated prediction pipeline.

The working STM32 firmware was developed separately; this checkout contains its Python transport, not a reproducible STM32 firmware build. The physical demo requires the board already running the confirmed ASCII-command firmware.

## Windows setup

Use Python 3.11 or newer. From the repository root in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r wildlife_watch/hardware/requirements-serial.txt
```

No virtual-environment activation is required. OpenCV supplies the NumPy dependency; the serial requirements file supplies pyserial. No model downloads or training are needed.

For calibrated live demos, first follow [camera calibration](docs/MARKER_POSE.md) and [marker-to-deer geometry](docs/DEER_LOCALIZATION.md). The commands below use the existing demo laptop's `runs/logitech-calibration.json` and `runs/deer-geometry.json`. **These local files are intentionally not committed. A fresh clone must create its own calibration and measured target geometry before running these commands.** Do not substitute invented intrinsics or example dimensions. Camera index `1` and marker side `7.00` cm must match your actual setup. Calibration must match the 640 x 480 capture mode and camera optics.

## Live camera with mock motors

This command uses the real webcam and pose pipeline, with no physical motor connection:

```powershell
.\.venv\Scripts\python.exe -m wildlife_watch.collision_demo --hardware-backend mock --config docs/collision_demo.synthetic.json --allow-synthetic-config --calibration runs/logitech-calibration.json --marker-side-cm 7.00 --target-geometry runs/deer-geometry.json --camera 1 --backend dshow --width 640 --height 480 --fps 30 --fourcc MJPG
```

The collision geometry and stopping assumptions in this demonstration config are **synthetic**, visibly labeled on screen. A visually aligned deer box does not establish measured vehicle geometry or stopping performance.

## Separate STM32 wheels-raised demonstration

**Real motors can turn.** Secure the vehicle with all driven wheels raised, keep hands/cables clear and the motor-power disconnect reachable. Close other COM8 applications. This explicit opt-in is for an output demonstration, not ground driving:

```powershell
.\.venv\Scripts\python.exe -m wildlife_watch.stm32_bench_demo --confirm-wheels-raised-and-disconnect-ready --port COM8 --config docs/collision_demo.synthetic.json --allow-synthetic-config --calibration runs/logitech-calibration.json --marker-side-cm 7.00 --target-geometry runs/deer-geometry.json --camera 1 --backend dshow --width 640 --height 480 --fps 30 --fourcc MJPG
```

- Startup is stopped and disarmed. Focus the OpenCV window; press **A** only after stable TRACKED + LOW risk. A fresh observation is required before PWM is sent.
- **S** latches STOP. **Q/Esc** exits and requests STOP. Disconnect motor power immediately if the application or USB becomes unresponsive.
- Even one missed marker frame latches STOP. Fresh LOW tracking plus another deliberate **A** is required to restart. Do not hold A to defeat the latch.
- PWM 200 may stall the motors. Neither PWM mapping is a calibrated speed.
- Append `--diagnostics` for ARM, command, ACK and exact STOP-trigger logs.

See [wheels-raised instructions](docs/STM32_WHEELS_RAISED_DEMO.md) and [measured physical-backend requirements](docs/STM32_BENCH.md). The separate demonstration ignores example stopping parameters and computes no stopping margin; it does not weaken the normal physical backend's measurement gates.

## Automated verification

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s wildlife_watch -t . -p "test_*.py" -v
```

Tests use synthetic images/observations and fake serial: pose/projection, relative motion, collision cases, tracking loss, latches, serial ACKs/faults and diagnostic events. They do not connect COM8, actuate motors or validate physical braking. Earlier Arduino C++ logic tests are documented in [firmware/README.md](firmware/README.md).

## Current limitations

- Marker-assisted localization is not recognition of unmarked wildlife.
- Motion blur, occlusion and marker orientation can interrupt detection. Recorded physical-demo stops were triggered by marker loss; the stop latch behaved as designed.
- Demo collision geometry/stopping assumptions are synthetic. Calibration and target measurements are setup-specific; visual alignment alone proves no accuracy.
- Camera rotation, buffering and derivative-filter lag affect relative motion. Constant-velocity, straight-driving prediction is an approximation.
- STOP coasts. Stopping distance, response bounds and autonomous ground-driving collision avoidance have not been validated. The firmware's 2-second watchdog is not evidence of timely collision prevention.
- The dashboard shows requested/acknowledged duty, not measured wheel speed.
- Historical design documents retain the WildCross/Wildlife Watch names and earlier plans; this README describes the current hackathon demonstration.

## Future improvements

Measure vehicle/target geometry, coast stopping distance and end-to-end latency; improve camera mounting, lighting and exposure reliability; integrate independent ToF measurements; then validate controlled low-speed tests with appropriate physical interlocks. Unmarked wildlife recognition is a later research step.

## Repository guide

- [Vision and pose](docs/MARKER_POSE.md), [ArUco diagnostics](docs/ARUCO_WEBCAM.md)
- [Deer localization](docs/DEER_LOCALIZATION.md), [collision demo](docs/COLLISION_DEMO.md)
- [STM32 demo](docs/STM32_WHEELS_RAISED_DEMO.md), [STM32 integration](docs/STM32_BENCH.md)
- [Mechanical work](mechanical/README.md), [contributing](CONTRIBUTING.md)

No open-source license has been selected yet.

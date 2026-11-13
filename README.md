# Wildlife Watch

**A low-cost wildlife-aware RC car that slows down or brakes when an animal crosses its path.**

We are building a 3D-printed RC car with four DC motors, a top-mounted Logitech webcam, and a thermal camera. It travels forward along a straight test lane. A laptop processes the camera feeds, estimates position, distance, and severity, and sends commands over USB to a microcontroller controlling the motors through H-bridge drivers.

This is an RC-scale demonstration of a collision-mitigation concept. It is not validated for a full-size car. There is no drone or steering in this MVP.

## Intended behavior

| Situation | Requested response |
| --- | --- |
| Operator has armed the car; perception and communication are healthy; no relevant hazard | Forward at a tested cruise setting |
| Farther wildlife within the travel corridor | Reduce drive to a tested slow setting |
| Immediate hazard within the measured stopping threshold | Request braking immediately; latch the stop |
| Stale perception, lost USB commands, or a fault | Stop request; never retain the last forward command indefinitely |
| Hazard stop or fault has occurred | Explicit operator re-arm before moving again |

These are planned rules, not working firmware. “Immediately” means requesting braking without an intentional delay, not zero stopping time. The motor driver's physical brake behavior and the thresholds must be measured.

## Who builds what

| Owner | Responsibility | Location |
| --- | --- | --- |
| JerisonTIan1 | Wiring, power, motor drivers, and microcontroller firmware | `firmware/`, `docs/HARDWARE.md` |
| Teammate, to be agreed | CAD, 3D printing, chassis assembly, and mounts | `mechanical/` |
| Teammate(s), to be agreed | Camera input, wildlife detection, position/distance, severity, and USB sender | `wildlife_watch/` |
| Whole team | Interface agreement and physical integration tests | `docs/` |

Teammates: [marvinuofa](https://github.com/marvinuofa) and [VyomMaheshwari1](https://github.com/VyomMaheshwari1). Their individual workstream split is not assigned here.

## Current status

The repository contains a camera/video preview utility and a **dry-run motor-controller sketch**, with USB command parsing, four-motor output intent, arming, latched stop states, and a command watchdog. The sketch compiles for Uno and classic Nano; its control logic has host tests. **It drives no motor pins.**

The chassis, live H-bridge backend, laptop command sender, detector, range estimator, and physical automatic braking remain to be built. Start your Arduino work with [firmware/README.md](firmware/README.md).

The preview passed synthetic-video checks. Physical-camera compatibility and physical vehicle behavior have not been verified. Two preview feeds are displayed side by side; they are not synchronized or fused.

## Run the preview

Use Python 3.11 or newer:

```sh
python -m venv .venv
```

Activate on Windows PowerShell with `.venv\Scripts\Activate.ps1`, or macOS/Linux with `source .venv/bin/activate`.

```sh
python -m pip install -r requirements.txt
python -m wildlife_watch.preview --rgb 0
python -m wildlife_watch.preview --rgb 0 --thermal 1
python -m wildlife_watch.preview --rgb data/rgb.mp4 --thermal data/thermal.mp4
```

Use `--thermal 1` only if the thermal camera exposes an OpenCV-compatible video device. Proprietary/radiometric cameras may need a manufacturer SDK adapter. Camera indices depend on the machine.

Press Q or Escape to close. Video files run as fast as decoding permits; playback is not time-aligned. The first ended/failed source stops the preview with a message. Live camera read failure returns a nonzero exit code. This utility neither records footage nor commands motors.

## Build order

1. Identify the H-bridge, motor ratings, battery, and controller board; agree on the USB contract.
2. Test one motor, then all four, using manual commands with wheels raised.
3. Demonstrate link-loss stopping and measure low-speed braking distance.
4. Validate laptop detection, distance, and path relevance.
5. Integrate cruise, slow, brake, and fault cases in a bounded test lane.

Start with [architecture](docs/ARCHITECTURE.md), [control interface](docs/CONTROL_INTERFACE.md), [firmware](firmware/README.md), [mechanical design](mechanical/README.md), [hardware/cost](docs/HARDWARE.md), [evaluation](docs/EVALUATION.md), and [backlog](docs/BACKLOG.md).

## Working together

Use small branches and pull requests; see [CONTRIBUTING.md](CONTRIBUTING.md). Keep raw recordings, model weights, credentials, and generated media out of Git. Record model/dataset permissions. No open-source license has been selected yet.

Use “low-cost” as the headline; the preliminary cost estimate and missing bill-of-materials details live in the hardware document. A staged model-animal or warm-proxy demonstration tests parts of the pipeline, not real deer recognition or full-size collision prevention.

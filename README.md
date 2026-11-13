# Wildlife Watch

**A low-cost, vehicle-mounted wildlife warning prototype using a Logitech webcam and a thermal camera.**

We want to help a driver notice wildlife near the vehicle's path, especially when the visible-light image is difficult to interpret. Our approach combines a roof-mounted Logitech webcam with a thermal camera and a simple warning interface.

The team's preliminary hardware estimate is **approximately $700, including the thermal camera**. Currency, itemized costs, and compute inclusion still need confirmation. The motivation is straightforward: a modest add-on relative to the cost of a car. This is a prototype cost estimate, not a verified retail price or evidence of collision prevention.

## Current status

This repository is the team starter. It contains a working camera/video preview utility and a plan for building and measuring the detector. **Animal detection, thermal/RGB fusion, and driver alerts are not implemented yet.** No drone is part of this project.

| Component | Status |
| --- | --- |
| Webcam or recorded-video preview | Implemented; synthetic-video smoke test |
| Two sources displayed side by side | Implemented for OpenCV-compatible sources; not synchronized |
| Exact Logitech and thermal hardware | Models and interfaces to confirm |
| Wildlife detector | To implement and evaluate on target species |
| Thermal evidence and cross-camera association | To implement after capture and calibration |
| Driver warning UI | To implement; never equate no detection with a clear road |
| Vehicle tests and collision-prevention benefit | Not validated |

## Get started

Use Python 3.11 or newer. From the repository root:

```sh
python -m venv .venv
```

Activate on Windows PowerShell with `.venv\Scripts\Activate.ps1`, or on macOS/Linux with `source .venv/bin/activate`.

```sh
python -m pip install -r requirements.txt
python -m wildlife_watch.preview --rgb 0
```

Camera numbers depend on your computer. Use `--thermal 1` only if the thermal camera exposes a compatible video device. Otherwise, implement the manufacturer's SDK adapter first; this script does not decode proprietary or radiometric thermal data.

```sh
python -m wildlife_watch.preview --rgb 0 --thermal 1
python -m wildlife_watch.preview --rgb data/rgb.mp4 --thermal data/thermal.mp4
python -m wildlife_watch.preview --rgb data/rgb.mp4 --headless --max-frames 30
```

Press **Q** or **Escape** to close the preview. Video files run as fast as decoding permits; playback is not time-aligned. The first ended/failed source stops the preview with a message. Live capture failure returns a nonzero exit code. No footage is recorded by this utility.

## Team workflow

- Owner: [JerisonTIan1](https://github.com/JerisonTIan1)
- Teammates: [marvinuofa](https://github.com/marvinuofa), [VyomMaheshwari1](https://github.com/VyomMaheshwari1)
- Claim one task in [the backlog](docs/BACKLOG.md), open a short branch, and submit a pull request.
- Start with [CONTRIBUTING.md](CONTRIBUTING.md). Coordinate ownership before editing a shared module.
- Invite status is managed by GitHub; listing a teammate here does not grant access.

## Build priorities

1. Identify both cameras and demonstrate repeatable capture.
2. Evaluate an RGB baseline on actual target wildlife footage.
3. Add thermal evidence and measure whether it improves results over RGB alone.
4. Build a clear warning/fault interface and record a repeatable demo.
5. Finish the bill of materials and publish measured limitations alongside results.

See [architecture](docs/ARCHITECTURE.md), [hardware and cost](docs/HARDWARE.md), [evaluation](docs/EVALUATION.md), and [backlog](docs/BACKLOG.md).

## Scope and limitations

This is an experimental assistive warning concept. It does not control steering or braking, establish a safe driving speed, or replace driver attention. Start with stationary, controlled demonstrations. Detection range, low-light performance, false alarms, and latency must be measured before making road-use claims. Heat alone is not proof of an animal, and an RGB model cannot be assumed to work on thermal imagery.

Keep raw footage, model weights, credentials, and identifiable location data out of Git. Record dataset permission and model licenses before sharing assets. No open-source license has been selected yet; the team should agree before public distribution.

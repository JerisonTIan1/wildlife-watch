# RC-car architecture

## Confirmed scope

- 3D-printed chassis, four DC motors, forward-only travel along a straight test lane.
- Top-mounted Logitech webcam and thermal camera.
- Laptop perception with USB communication to the motor controller.
- Jerison handles wiring and motor firmware; teammates handle mechanical design and perception.
- H-bridge motor drive; exact module and motor/power ratings remain open.
- Uno, Nano, or ESP32 controller under consideration; exact board remains open.

## Proposed pipeline

```text
Logitech webcam ----+
                    +-> laptop: detection -> position/range -> path relevance -> risk
Thermal camera -----+                                                         |
                                                                         USB serial
                                                                              |
                     4 DC motors <- H-bridge(s) <- controller state + watchdog
                                                                              |
                                                          status back to laptop
```

Only the camera preview is implemented. The rest is a proposed design.

## Perception boundary

The laptop determines object identity, position relative to the travel corridor, range, and uncertainty. It sends a risk mode, not raw pixel coordinates, to the controller.

A bounding box does not automatically provide metric distance. For an initial constrained demo, investigate calibrated ground-plane geometry and validate against measured target locations. If those assumptions do not fit the setup, choose another ranging method before claiming distance.

RGB plus thermal does not automatically make a depth camera. Stereo ranging requires known geometry and corresponding image points. Our design inference is that cross-spectrum matching requires its own validation. [OpenCV stereo-depth tutorial](https://docs.opencv.org/4.x/dd/d53/tutorial_py_depthmap.html).

Determine whether thermal output is video, raw sensor values, or calibrated temperature. Do not assume an RGB model works on thermal frames. Define a conservative disagreement policy; a credible immediate obstacle must not be ignored solely because the second sensor disagrees.

## Controller states to implement

| State | Motor intent | Exit |
| --- | --- | --- |
| DISARMED | No forward drive | Deliberate operator arm with healthy fresh input |
| CRUISE | Tested forward setting | Far hazard, brake request, or fault |
| SLOW | Reduced forward setting | Brake/fault, or stable clearance under hysteresis |
| BRAKE_LATCHED | Driver-specific brake request | Operator re-arm after clearance |
| FAULT_LATCHED | Driver-specific stop request | Fault resolved and operator re-arms |

“Immediate braking” means prompt actuation, not instantaneous physical stopping. Choose thresholds using measured speed, perception/communication delay, braking distance, and range uncertainty. Unknown in-path obstacles must not be considered safe simply because they are not classified as deer.

Equal motor PWM does not guarantee straight travel or a known speed. Verify drift in the intended lane. No steering or reverse operation is required.

## Build sequence

One motor on the bench -> four motors with wheels raised -> manual USB commands -> measured low-speed lane tests -> real perception integration.

See [control interface](CONTROL_INTERFACE.md) and [evaluation](EVALUATION.md). Use staged targets for the RC demo and label proxy evidence honestly.

# Live camera to prediction to mock braking

Optional [USB serial bench/integration](USB_SERIAL.md) is now available behind
explicit operator flags. Mock remains default. Serial mode rejects synthetic
configurations, disables tracking-loss grace, and accepts only the documented
SIM firmware endpoint. The instructions below describe mock operation.

This MVP reuses `marker_pose.Observation`, the calibrated webcam callback and
`MockCarController`. No serial port or physical motor controller is opened.
Firmware, ToF, calibration and motor-driver code are unchanged.

## Run on Windows

Use your real calibration file, measured marker side and working camera settings.
The command below uses **synthetic geometry and braking numbers solely to exercise
the mock**. `7.00` is appropriate only if your measured marker side is 7.00 cm:

```powershell
.\.venv\Scripts\python.exe -m wildlife_watch.collision_demo --config docs/collision_demo.synthetic.json --allow-synthetic-config --calibration runs/logitech-calibration.json --marker-side-cm 7.00 --camera 1 --backend dshow --width 640 --height 480 --fps 30 --fourcc MJPG
```

The synthetic label stays visible. It does not make the calibration or pose
synthetic: it means the corridor and stopping performance are illustrative.
No measured vehicle dimensions or braking results have been invented.

Wait for valid pose and velocity warmup. Press **A** to deliberately arm/re-arm
only on fresh LOW risk with available braking parameters. The next observation
may request motion. **S** latches a stop; **Q/Escape** exits and stops the mock.
Startup/loss/warmup produce UNKNOWN; by default they request STOP (see bounded
tracking-loss experiments below). A later LOW never automatically
releases a stop latch. After slowing, duty stays at or below the slowed value
until explicit A re-arm. The display separates policy level from applied mock
duty/state: NORMAL can be requested while the mock remains stopped.

The existing image/marker/pose display is extended with risk, time to conflict,
policy level/reason, mock state/duty and operator controls. No frontend framework.

## Replace illustrative configuration

Copy the JSON to a local file, supply actual measurements and set `synthetic` to
false only when the geometry and braking inputs are genuinely sourced. It remains
a mock; the label is not a verification mechanism. For unavailable braking data,
set `stopping_distance_cm` and/or `response_delay_s` to `null`: policy remains STOP,
arming is denied, and geometric risk still displays.

| Parameter | Meaning |
| --- | --- |
| vehicle_width_cm | Full width of the car |
| camera_to_front_cm / camera_to_rear_cm | Optical-center distances to front/rear vehicle limits |
| target_half_width_cm / target_half_depth_cm | Bounding extents about marker center, enclosing the simulated deer/trolley |
| margin_cm | Added geometric uncertainty allowance in both axes |
| horizon_s / high_risk_s | Prediction horizon / urgent-conflict threshold; tunable, not physical measurements |
| stale_s / max_reprojection_px | Freshness and pose-quality gates; initial tuning values |
| normal_duty / slow_duty | Integer requested PWM percentages; never measured speed |
| stopping_distance_cm | Future measured conservative stopping-distance bound from stop actuation at the largest permitted duty/load |
| response_delay_s | Future conservative processing/communication/actuation delay allowance |

Use target extents that enclose the whole trolley relative to its marker, not the
marker's 70 mm width. The camera is assumed on the vehicle centerline and aligned
with straight travel. For an offset/tilted mount this geometry is not valid until
an appropriate coordinate transform or sufficiently justified bounds are added.

## Prediction model

`collision.CollisionPredictor.update(observation, now)` accepts the existing
Observation (or `None` for missing data). `now` and receipt timestamps must share
the `perf_counter()` clock domain. Validity, ID, finite values, reprojection error,
timestamp order and age are checked. Stale/future/invalid data clears lateral
history and returns UNKNOWN with no current conflict estimate.

Lateral velocity is a least-squares slope of fresh X values over <=0.3 s / 30
samples, requiring >=3 samples spanning >=0.08 s. Existing closing speed is reused.
The model propagates `x(t)=x+vx*t`, `z(t)=z-closing*t`, including receipt-to-decision
age. It intersects the time intervals when both coordinates occupy an expanded
vehicle rectangle:

- X: plus/minus (vehicle width / 2 + target half width + margin).
- Z: from -(camera-to-rear + target half depth + margin) to
  camera-to-front + target half depth + margin.

The first simultaneous overlap within the horizon is `conflict_in_s`. A target
can cross the lane and still be LOW if it clears before longitudinal overlap.
Stationary separated targets and receding targets are LOW when no overlap occurs.
Current geometric overlap is HIGH even without a speed estimate.

- **HIGH:** overlap now or predicted within `high_risk_s`.
- **MEDIUM:** predicted overlap later within the horizon.
- **LOW:** no overlap under this model within the horizon. This is not “road clear.”
- **UNKNOWN:** missing/invalid/stale data or insufficient velocity history.

`RiskDecision` exposes risk, reason, decision timestamp, conflict/time, lateral
speed, forward clearance and closing speed. Predictions expire: call `update(None,
now)` during missing data rather than reusing an old decision.

## Braking policy and limitations

HIGH/UNKNOWN -> STOP. Missing braking parameters -> STOP even on LOW.
For a predicted conflict, stopping margin is forward clearance minus configured
stopping distance minus positive closing speed times response delay. Nonpositive
margin -> STOP; otherwise MEDIUM -> SLOW. LOW with braking inputs -> NORMAL.
`BrakeDecision` includes the requested duty and stopping margin where applicable.

This margin is a conservative trigger heuristic, **not a validated physical
collision-avoidance guarantee**: target motion during braking, rotational camera
motion, acceleration, skid, drivetrain lag and uncertainty are not modeled.
It does not infer car speed or deceleration from duty or relative closing speed.
The fixed bound must cover the maximum configured operating duty before physical
use. STOP calls the mock's latched `stop()`, not `set_speed(0)` as a claim of active
braking. Actual brake/coast behavior remains unvalidated.

By default loss immediately requests STOP. Long loss after HIGH stays
UNKNOWN/stopped rather than decaying to LOW. A stop latch requires deliberate
operator re-arm. No blind persistence of old pose. The demo now runs independent
mock freshness checks as described below; it still must not be reused as a
physical motor controller.

## Bounded tracking-loss experiments (mock only)

**Perception risk and control action are separate.** A missed marker, failed read
or stale frame reports UNKNOWN, never LOW or a current predicted trajectory.
The overlay distinguishes TRACKED (fresh accepted pose, possibly velocity warmup),
TEMPORARILY LOST (within the bound) and LOST, with age since the last accepted pose.
Last known risk and pose appear only as HISTORICAL with their ages. Historical
risk age can exceed pose age during velocity warmup; neither is a current risk.

An optional `tracking_loss` object may be added to the config:

```json
"tracking_loss": {
  "grace_s": 0.15,
  "capture_timeout_s": 0.075,
  "measured_bounds": false,
  "stopping_distance_bound_cm": null,
  "relative_speed_bound_cm_s": null,
  "latency_bound_s": null
}
```

Omission uses these defaults. Grace is bounded to 0..500 ms (initial experiment:
150 ms). **This does not by itself enable continued motion:** absent measured
bounds still means STOP on the first loss. Synthetic configuration cannot set
`measured_bounds: true`; its warning stays visible. No physical measurements are
supplied by this change. Unit-test bound values are explicitly synthetic fixtures.

Only after measurements are supplied in a non-synthetic configuration may you
declare `measured_bounds: true`. The declaration is user attestation, not an
automated validation. Required positive bounds must cover:

- Stopping distance after STOP under the maximum permitted operating duty, load,
  surface and drivetrain condition, including the initially higher duty.
- Maximum **relative** speed magnitude (car and target motion), not PWM percentage.
- Worst-case relevant sensing/filtering/processing/actuation latency. Include
  sensor buffering and the delayed response of reduced duty; a camera timestamp
  alone does not measure these.

The provisional SLOW request reserves historical forward clearance minus the
stopping-distance bound minus relative-speed bound times (the **entire** grace
interval + latency bound + 10 ms polling allowance). Margin must be positive and
last observed relative speed must not exceed the bound. It never increases applied
duty and never releases a stop latch. It is a reduced-duty request, **not a claim
of coasting or active braking**. Unknown standard braking calibration still blocks
arming through the existing policy.

The deadline starts at the last fully valid risk measurement, not the first miss.
Missing frames and velocity warmup do not move it. HIGH history immediately stops;
grace expiry stops; insufficient/exhausted bounds stop. Three loss episodes within
one second trigger a flicker stop. Brief reacquisition cannot clear that stop or
reset the recent-loss count. Explicit A on fresh LOW is required to clear the
latch and reset the flicker guard. Warmup after loss can itself exhaust the grace;
the implementation deliberately does not extend it merely to keep the demo moving.

The wrapper starts a separate worker that checks freshness every 10 ms using the
same monotonic clock. After 75 ms without a callback (configurable up to 150 ms),
it produces UNKNOWN and evaluates the loss policy independently of the camera.
It also ticks the existing mock watchdog. Callback/control/key/overlay access is
serialized with a lock. The worker stops and joins on exit; exceptions latch STOP.
A frozen camera window can remain visibly frozen, but it does not refresh motion
commands. The worker can stop the mock without any callback or overlay refresh.

Python threads and Windows scheduling are **not hard real-time**; process crashes,
GIL-holding native calls or scheduler stalls can delay this worker. This architecture
is mock-only and is not a substitute for the independent Arduino watchdog or
physical stop system. No firmware, calibration, pose mathematics or physical
controller integration was changed.

Camera-axis velocity includes motion from camera yaw/pitch and vibration. The
straight-driving constant-relative-velocity approximation is valid only in a
controlled lane with a rigid aligned camera and short smooth-motion intervals.
The geometric margin does not constitute a quantified uncertainty model. PnP
ambiguity, blur, target occlusion, filter lag and driver buffering still matter.
Only marker ID 0 is modeled, not unmarked obstacles or a generally clear road.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest wildlife_watch.test_tracking_loss wildlife_watch.test_collision wildlife_watch.test_marker_pose wildlife_watch.test_aruco_webcam wildlife_watch.hardware.test_hardware -v
```

All collision scenarios use explicitly **synthetic** dimensions, trajectories and
braking parameters. Cases cover approaching, outside path, crossing in, crossing
clear, stationary/receding, current overlap, missing/stale data, prolonged loss
after danger, braking calibration unavailable, stopping margin, explicit stop
latches, stale re-arm rejection, no automatic duty increase and demo callback wiring.
Physical live-camera integration and braking have not been validated by the agent.
Local verification: all 48 combined tracking-loss, collision, pose, webcam and mock-hardware
tests passed on Python 3.13/OpenCV 4.14.0. CLI help and Python compilation passed.

For the live demo, first use a stationary camera and move the trolley through
those cases, noting risk, conflict time, policy and mock state. Confirm removing
the marker immediately shows UNKNOWN. Without measured loss bounds it must STOP;
with the gate satisfied only the bounded reduced-duty interval is allowed before
STOP. Replacing the marker must not release a latched stop or increase duty.
Then repeat on the mounted car without connecting software to motors.

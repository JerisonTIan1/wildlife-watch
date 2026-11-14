# NUCLEO-G431KB USB integration — wheels raised only

The `stm32` backend is separate from the existing `serial` V1/SIM backend.
It uses the confirmed ST-LINK VCP protocol at 115200 baud:

| Action | Bytes | Required reply |
| --- | --- | --- |
| NORMAL | `120\n` by default | `PWM = 120` |
| SLOW | `80\n` by default | `PWM = 80` |
| STOP | `STOP\n` | `STOPPED` |

`--normal-pwm` / `--slow-pwm` configure raw 0..255 PWM, not percentages or measured
speed. `TIMEOUT - STOPPED` faults the session; it is not permission to resume.
No V1, ARM or DISARM wire commands are sent. Arming and stop latches are enforced
on the host. Firmware and pin assignments are unchanged.

**STOP disables TB6612FNG outputs into standby/coasting. It is not validated active
braking. The firmware's 2000 ms watchdog is too slow to claim actual collision
prevention.** This integration is for a secured, wheels-raised bench only. Keep a
motor-power disconnect reachable. The supplied protocol has no sequence/session
identifier: silent resets and delayed identical replies cannot be reliably
distinguished. This is not a safety-rated protocol or controller.

## Current gate: measurements are missing

The workspace had calibration and deer geometry, but no measured vehicle/stopping
config at implementation time. Physical demo activation stays disabled until a
non-synthetic config and measurement record are supplied. No measurement file or
verified values have been fabricated. Use mock mode below in the meantime.

Create `runs/collision.measured.json` using the existing collision/braking schema
from [COLLISION_DEMO.md](COLLISION_DEMO.md), replacing every illustrative value
with actual measurements and setting `synthetic: false` only after doing so.
Add this metadata with real results (nulls below deliberately fail validation):

```json
"stm32_bench_measurements": {
  "vehicle_and_target_geometry_measured": false,
  "coast_stopping_measured": false,
  "latency_measured": false,
  "max_relative_speed_cm_s": null,
  "max_pwm_tested": null,
  "measurement_record": "runs/stm32-measurements.md"
}
```

Required evidence:

- Vehicle width and optical-center-to-front/rear distances; target envelope and
  marker-to-body offsets; match the rigid mounted camera/target geometry.
- Coast stopping-distance bound at the largest permitted raw PWM, representative
  battery/load/surface; record trial results and conservative bound in
  `braking.stopping_distance_cm`. Wheel rotation in air does not measure ground
  stopping distance. Arrange controlled measurements separately; this integration
  does not authorize or execute a ground-driving test.
- Relative-speed operating bound (including target motion), and maximum tested PWM.
  Normal PWM must not exceed it. Observed relative velocity above the bound stops.
- Measured worst-case camera/filter/processing/link/actuation latency in
  `braking.response_delay_s`. The gate requires at least 0.18 s to budget the
  configured 50 ms write + 120 ms acknowledgment + 10 ms polling; add upstream
  measured delay. This floor is an engineering budget, not a measurement or a
  guarantee of Windows scheduling latency.

Set each attestation true only after measurement, and create a nonempty record
file with results, conditions, date and operator. The code checks presence and
declared bounds, not whether your written measurements are truthful. Relabeling
synthetic values is not verification. Configured percentage duties still describe
mock/V1 policy output; STM32 maps the policy action directly to its raw PWM values.

## Exact PowerShell commands

From the repository root; replace camera index, calibration path and
marker size with your actual setup (`7.00` only for a measured 7.00 cm black square).

Install the existing optional serial dependency, without opening any port:

```powershell
.\.venv\Scripts\python.exe -m pip install -r wildlife_watch/hardware/requirements-serial.txt
```

**A. Safe mock end-to-end demonstration** (synthetic corridor/brakes remain labeled):

```powershell
.\.venv\Scripts\python.exe -m wildlife_watch.collision_demo --hardware-backend mock --config docs/collision_demo.synthetic.json --allow-synthetic-config --calibration runs/logitech-calibration.json --marker-side-cm 7.00 --target-geometry runs/deer-geometry.json --camera 1 --backend dshow --width 640 --height 480 --fps 30 --fourcc MJPG
```

**B. Physical wheels-raised bench**, only after supplying the measured config above:

```powershell
.\.venv\Scripts\python.exe -m wildlife_watch.collision_demo --hardware-backend stm32 --enable-physical-bench --port COM8 --normal-pwm 120 --slow-pwm 80 --config runs/collision.measured.json --calibration runs/logitech-calibration.json --marker-side-cm 7.00 --target-geometry runs/deer-geometry.json --camera 1 --backend dshow --width 640 --height 480 --fps 30 --fourcc MJPG
```

Close Serial Monitor/other COM8 users. Startup sends STOP, requires STOPPED and
starts disarmed; camera initialization cannot send NORMAL. Wait for fresh LOW risk
and press **A**. Arming sends no PWM; a subsequent fresh valid observation can
request motion. **S** latches STOP; later LOW cannot restart it. Re-arm requires A.
After SLOW, automatic increases remain prohibited until explicit re-arm.

**C. Emergency shutdown**:

1. Press **S** in the focused demo window, or **Q/Escape** / terminal **Ctrl+C** to
   stop and close. If software is unresponsive or STOP is not confirmed, use the
   physical motor-power disconnect immediately; do not wait for a terminal command.
2. If the demo has exited and COM8 is free, the STOP-only utility is:

```powershell
.\.venv\Scripts\python.exe -m wildlife_watch.hardware.stm32_stop --port COM8
```

It only sends STOP, never PWM. A second process cannot reliably stop a port still
owned by the demo. Even acknowledged STOPPED means disabled outputs/coasting,
not zero physical velocity. Never use `stm32_usb_test.py` as an emergency-stop
command: that pre-existing test intentionally sends a nonzero PWM.

## Freshness, acknowledgments and failure behavior

Only valid camera callbacks request motion. Same-duty requests are capped at 10 Hz;
reductions and STOP bypass that limiter. No timer replays cached NORMAL. Each write
requires an unexpired observation; expiry during acknowledgment handling also
requests STOP. Invalid/stale/lost/warmup observations always STOP on physical
backends, regardless of mock grace configuration. The independent freshness
worker ticks the controller and requests STOP if capture freezes.

Reads are nonblocking, writes have a 50 ms timeout, and acknowledgment waits are
bounded to 120 ms. Replies may arrive fragmented. A wrong/missing acknowledgment,
partial write, USB exception or unexpected asynchronous status faults the host
session, clears acknowledged motor status to UNKNOWN, and attempts STOP. No PWM
retry, reconnect, or automatic re-arm occurs. A faulted session must be closed and
deliberately reopened. Best-effort STOP can fail on unplug; the two-second firmware
timeout is the fallback, not an emergency-braking guarantee. Silent resets cannot
be reliably identified without changing the firmware protocol.

The existing dashboard layout is unchanged. Its state/duty represent acknowledged
board output requests; the footer reports raw requested PWM separately from the
last acknowledgment. On serial errors, acknowledgment becomes UNKNOWN. Neither is
physical wheel-speed feedback. Policy percentage settings are not the raw STM32
PWM mapping—refer to the request/ACK footer.

Python threading is not hard real-time. The control lock serializes port operations;
an in-flight bounded write/ack wait can delay a freshness stop. Process crashes,
OS stalls or native calls holding the GIL still require firmware/physical protection.

## Tests and scope

```powershell
.\.venv\Scripts\python.exe -m unittest wildlife_watch.hardware.test_stm32 -v
```

Fake-serial tests cover startup STOP, no actuation on arm, action mapping, rate
limits, stale deadlines, loss/freeze STOP, latch recovery restrictions, missing/wrong
ACKs, disconnection, partial write, firmware timeout/reset text, shutdown and
synthetic config/mock-mode isolation. Test numbers are synthetic fixtures only.
The agent did not open COM8 or actuate motors. Physical Python-to-motor success is
user-reported from `stm32_usb_test.py`, not validation of this integrated loop.
# Separate output-only demonstration

For the explicitly opted-in, secured wheels-raised webcam-to-motor demonstration
without stopping calibration, see [STM32_WHEELS_RAISED_DEMO.md](STM32_WHEELS_RAISED_DEMO.md).
That isolated entrypoint does not enable the measured physical backend below and
does not validate collision prevention.


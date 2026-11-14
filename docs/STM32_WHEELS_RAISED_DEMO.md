# Wheels-raised webcam-to-STM32 output demonstration

This separate entrypoint demonstrates real camera risk decisions driving real motor
outputs. It is **not ground driving, calibrated braking, or verified collision
prevention**. Secure the vehicle so it cannot move, raise all driven wheels, keep
hands/cables clear, and keep the motor battery/power disconnect within reach.
Close any serial terminal or USB test using COM8 first.

From the repository root, with the existing venv/dependencies:

```powershell
.\.venv\Scripts\python.exe -m wildlife_watch.stm32_bench_demo --confirm-wheels-raised-and-disconnect-ready --port COM8 --config docs/collision_demo.synthetic.json --allow-synthetic-config --calibration runs/logitech-calibration.json --marker-side-cm 7.00 --target-geometry runs/deer-geometry.json --camera 1 --backend dshow --width 640 --height 480 --fps 30 --fourcc MJPG
```

Use the camera index already validated on this laptop. `7.00` is the marker's
black-square side in cm; change it if your measured size differs. Reuse the aligned
deer geometry and calibration at their matching capture resolution.

The confirmation flag is an operator attestation that the vehicle is secured,
wheels are raised and power can be disconnected. Without it the port is not opened.
Startup sends STOP and leaves motion disarmed. The display identifies REAL STM32,
WHEELS-RAISED DEMO, synthetic geometry and no stopping model. Actual camera poses
feed the unchanged collision predictor; measurements are not synthesized.

- Focus the OpenCV window; wait for stable TRACKED and LOW risk, then press **A**.
  Arming alone sends no PWM; the next fresh LOW observation requests **255/255**.
- MEDIUM requests **200/255**. This can stall the motors. These are demonstration
  duties, not measured speeds. LOW after slowing does not automatically increase
  duty; explicit rearming on LOW is required.
- HIGH, UNKNOWN, even one lost marker frame, or stale observations request latched
  STOP. Reacquisition never restarts motors. Wait for stable LOW, then deliberately
  press **A** again if appropriate. Do not hold A down to defeat the latch.
- Press **S** to latch STOP. Press **Q** or **Esc** to exit (shutdown sends STOP and
  closes USB). Disconnect motor power after testing. Ctrl+C also runs cleanup.
- If the application/USB is unresponsive, **disconnect motor power immediately**.
  Do not depend on another process opening an already occupied COM port.

STOP disables outputs and **coasts**, not guaranteed active braking. The unchanged
firmware has a **2000 ms watchdog**. Host freshness checking is independent of
camera callbacks (75 ms deadline, 10 ms check interval), but Python/Windows timing
is not hard real time, and serial ACK/write waits add delay. A frozen PC or failed
USB may leave outputs running until the firmware timeout; physical disconnect is
essential. No physical stopping performance is established by this demo.

Motion writes are bounded to 10 Hz, except immediate reductions/STOP. Fresh valid
observations renew deadlines; the monitor never replays a motion command. Missing
or unexpected ACKs latch a fault and require restarting the application after the
fault is resolved. Requested action/PWM and ACK status remain separate on screen.
The SLOW percentage is rounded to 78%; the exact wire command is always `200`.

The JSON's braking/stopping and tracking-loss grace settings are deliberately not
used in this isolated output demonstration. Collision geometry still comes from
the JSON and is prominently labeled synthetic/unverified. No stopping margin is
computed. The normal `collision_demo --hardware-backend stm32` entrypoint and its
measured geometry, stopping-distance, latency, speed-bound and evidence gates are
unchanged. This demonstration does not satisfy those gates or authorize ground use.

Automated validation uses fake serial and synthetic observations only:
`python -m unittest wildlife_watch.test_stm32_bench_demo wildlife_watch.hardware.test_stm32`.

## Diagnosing brief motion followed by STOP

Add `--diagnostics` to the launch command. This enables JSON event lines in the
terminal alongside the existing camera diagnostics; it changes no safety limits.
Optionally capture the terminal with PowerShell `2>&1 | Tee-Object runs/stm32-diagnostic.log`.

Read the first `event: "STOP"` after `event: "ARM"`, not just the final STOPPED
ACK. `t_s` is a monotonic timestamp in seconds (not wall-clock time).
`observation_age_s` is age of the last predictor-accepted pose, including valid
pose/velocity warmup; it does not imply current perception is valid. `callback_age_s`
is time since the last camera callback. `risk`, `risk_reason`, `tracking`, and
`policy_reason` describe the state immediately before the stop request. A controller
deadline can expire while the last reported risk still says LOW; check the ages.
`last_pwm`, `since_motor_command_s`, and `last_ack` preserve the last attempted PWM
write and the latest accepted STM32 ACK before STOP overwrites the status.
`TX` means a write attempt, not proof of delivery; `ACK` confirms the expected reply.

| STOP trigger | Meaning |
| --- | --- |
| HIGH_RISK | Predictor returned HIGH. |
| UNKNOWN_RISK | Check risk_reason: e.g. velocity warmup, invalid pose or timestamp. |
| MARKER_LOSS / MISSING_OBSERVATION | Detection invalid / no observation supplied. |
| STALE_OBSERVATION | Incoming observation already older than 75 ms. |
| STALE_CAMERA_CALLBACK | Independent check found no callback for at least 75 ms. |
| CONTROLLER_WATCHDOG | Last observation's motor-command deadline expired; host watchdog, not firmware. |
| OBSERVATION_EXPIRED_BEFORE_COMMAND | Input deadline expired before sending PWM. |
| OBSERVATION_EXPIRED_DURING_ACK | ACK arrived, but the observation was already expired. |
| MISSING_ACK | No expected reply within the 120 ms ACK wait. |
| FIRMWARE_TIMEOUT | Received literal TIMEOUT - STOPPED from the STM32. |
| SERIAL_ERROR | Read/write failure or unexpected reply/reset; error contains detail. |
| MANUAL_STOP | Operator pressed S. |
| STARTUP / SHUTDOWN / OPERATOR_DISARM_BEFORE_ARM | Expected lifecycle STOP, including the explicit A rearm sequence. |
| FRESHNESS_WORKER_ERROR | Independent monitor raised an exception. |

Other policy/deadline validation reasons are logged verbatim. Already-latched
repeated stop requests do not flood the log or resend STOP; transport faults and
forced lifecycle stops are logged. Diagnostics are optional and terminal output
can itself add timing overhead; never relax safety deadlines to suppress a log.

At continuous 30 FPS, valid callbacks resend PWM about every 100–133 ms, well below
the firmware's 2000 ms timeout. The worker does **not** refresh PWM from cached data.
A 75 ms observation deadline can expire during a permitted 120 ms ACK wait, even
though the command eventually receives a valid ACK. This is an intentional fail-closed
path. These are possible causes identified in code; only a captured run establishes
which one caused a particular physical stop. Stopping still coasts; keep the power
disconnect ready.

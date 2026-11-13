# Nano USB transport: bench first

The Python transport now connects to USB serial. **The checked-in firmware is
still SIM-only and drives no GPIO.** A real USB connection does not imply real
motor control. Firmware still models four motor intents; the hardware teammate
must reconcile the two-motor build, exact driver, pin map, power and stop behavior.
This change does not modify firmware or invent a ToF protocol.

Only documented V1 `SIM` status is accepted. No `LIVE` status or live-backend
contract exists here, so unknown modes fail closed. A future live driver requires
an agreed status contract, reviewed local arm/reset interlock and measured stopping
behavior before this integration can claim physical capability. A device falsely
reporting SIM cannot be authenticated by this protocol.

## Windows installation and bench

From repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r wildlife_watch/hardware/requirements-serial.txt
.\.venv\Scripts\python.exe -m serial.tools.list_ports
.\.venv\Scripts\python.exe -m wildlife_watch.hardware.serial_bench --port COM5 --enable-serial
```

Replace COM5 with the Nano's listed port. Close Arduino Serial Monitor and other
port users. Upload the existing dry-run sketch for the **actual Nano variant**
using its appropriate Arduino IDE target; no upload is performed by these commands.
Keep motor power disconnected for bench validation. Opening the port may reset
the Nano. The transport waits up to four seconds for exactly a fresh
`V1,0,DISARMED,BOOT,0,SIM` status. If absent, deliberately reset while connecting
or close/reopen after checking the board; it never guesses a sequence or arms on
connection. Do not open against an operating vehicle.

Keys are explicit operator actions:

- **A**: DISARM then ARM; each transition must be observed. ARM does not move.
- **1..9**: one SPEED request at 10..90 percent. Press shortly after A (within
  the existing 500 ms MCU watchdog). There is no automatic command repeater.
- **B / Space**: latched BRAKE request.
- **Q / Ctrl+C**: request stop and close port.

Without another fresh command within 500 ms, the MCU faults; this intentionally
ends the bench session and requires explicit close/reopen/reset. Do not disable
the watchdog to accommodate typing. Held-key OS repeats are repeated operator
input; release keys to test watchdog expiry. Test ARM, a single low-duty SPEED,
BRAKE, watchdog expiry, unplugging USB, and reset with motor power disconnected.
Observe statuses as **intent**, not wheel speed or confirmed physical braking.

## Integrated camera demo

Mock remains default. Serial requires all three flags: `--hardware-backend serial`,
`--enable-serial`, and `--port`. It also requires non-synthetic geometry/braking
configuration with braking bounds present. **Do not relabel synthetic values to
bypass this gate.** While measurements are unavailable, use the bench tool above
and the existing mock demo.

Once the required measured config exists (example paths, replace camera/marker
values with your actual setup):

```powershell
.\.venv\Scripts\python.exe -m wildlife_watch.collision_demo --hardware-backend serial --enable-serial --port COM5 --config runs/collision.measured.json --calibration runs/logitech-calibration.json --marker-side-cm 7.00 --camera 1 --backend dshow --width 640 --height 480 --fps 30 --fourcc MJPG
```

The operator still presses A on fresh LOW risk to explicitly DISARM/ARM; S latches
STOP. Motion begins only with a subsequent fresh observation. Serial mode never
uses the mock loss-grace policy, even if configured: UNKNOWN always requests BRAKE.
The independent freshness worker detects callback freezes and requests BRAKE;
it never sends SPEED. Only a current observation callback may request SPEED, and
its expiry timestamp is checked immediately before the write. No old speed queue
or reconnect replay exists. Synthetic configs are rejected before the port opens.

## Status and fault semantics

The [existing protocol](CONTROL_INTERFACE.md) is unchanged: ASCII newline frames,
115200 baud, increasing 32-bit sequences. Status can coalesce and is **not a
guaranteed per-command ACK**. The transport permits one in-flight command and
waits up to 120 ms for matching sequence, state and requested duty. A timeout may
be a lost/coalesced status, not proof the MCU rejected the command; conservatively
the host faults instead of retransmitting motion. Status is never treated as
encoder/speed feedback. `SIM` is shown in the backend label.

PySerial uses nonblocking reads and a 50 ms write timeout. Fragmented records are
assembled with bounded buffering; malformed/unknown statuses, partial writes,
unexpected transitions, sequence mismatches, MCU faults, resets and disconnections
latch a host fault. A bounded best-effort BRAKE is attempted (with a newline to
terminate a partial command). That attempt may fail; the independent MCU watchdog
is the fallback for link loss, not a proof of physical braking. No further motion
is accepted in the faulted session. Explicit reconnect requires a fresh boot and
operator arming again; reconnect is never automatic.

Calls are serialized by the demo lock. A pending bounded serial operation can
delay the freshness worker; Python/Windows scheduling is not hard real-time.
Worst-case latency must include write/status waits. A silent/reset MCU is not
made safe by a Python thread alone; preserve the firmware watchdog and physical
power/stop provisions. The V1 protocol has no authenticated boot/session nonce:
fresh-boot handshake is a conservative operational requirement, not authentication.

## Automated verification

```powershell
.\.venv\Scripts\python.exe -m unittest wildlife_watch.hardware.test_serial -v
```

Fake serial tests cover fragmented status, explicit transitions and latch recovery,
missing status without motion retry, partial writes, disconnect, reset before
motion, denied transitions, expired observations, unexpected sequence/mode,
non-boot connection rejection, synthetic-config gating and camera-freeze stopping
without SPEED refresh. They require neither PySerial installation nor hardware.
No physical Nano, COM port, motor or ToF validation has been performed by the agent.
The combined fake-serial, tracking-loss, collision, pose, webcam and mock-controller
suite contains 59 tests. Python compilation and the bench CLI help also pass.

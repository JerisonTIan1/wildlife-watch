# Hardware integration (dry run)

Architecture: prediction code calls a controller; the mock stores motor intent.
`CommandEncoder` produces the equivalent serial bytes for a future transport.
The existing Arduino parser/state machine owns arming, stop latches, and a local
watchdog. Its `DryRunMotorDriver` stores intent without touching pins.
No perception, UI, camera capture, or wireless implementation lives here.

## Windows setup and mock test

From the repository root, use Python 3.11+ (`py -3.13` below selects an installed
version). No third-party dependencies or hardware are needed for this module.

```powershell
py -3.13 -m unittest wildlife_watch.hardware.test_hardware -v
py -3.13 -m compileall -q wildlife_watch/hardware
```

```python
from wildlife_watch.hardware import MockCarController

car = MockCarController()  # DISARMED, zero duty
car.arm()                 # deliberate operator action, never automatic recovery
car.set_speed(25)         # integer 0..100 forward duty percentage
print(car.state, car.speed_percent, car.requested_duty)
car.stop()                # latched brake request
```

Positive speed requires arming. `set_speed(0)` is equivalent to `stop()`.
After stopping/faulting, explicitly `disarm()`, then `arm()` before driving.
Repeated stop calls are allowed. Invalid API values raise without refreshing
the watchdog; denied motion raises `RuntimeError`. Send fresh drive commands
every 100 ms only while prediction input is healthy. At 500 ms without a drive
command after arming, the mock faults and requests zero duty. The mock evaluates
time on method/property access or `tick()`; it has no background thread. Inject
`clock=` for deterministic tests. It does not simulate inertia or stopping distance.

## Serial boundary

```python
from wildlife_watch.hardware import CommandEncoder

commands = CommandEncoder()
assert commands.arm() == b"V1,1,ARM\n"
assert commands.set_speed(25) == b"V1,2,SPEED,25\n"
assert commands.stop() == b"V1,3,BRAKE\n"
```

The encoder only returns bytes: it does not open a COM port, track MCU state,
verify a response, or send anything. Use one encoder/owner per boot session.
A future USB transport must write full frames at 115200 baud with bounded I/O,
monitor statuses, and handle partial writes, timeouts, reset and reconnect
without automatic arm/replay. Do not interpret successful encoding/writing as
accepted motion. There is intentionally no background command repeater that
could keep stale perception alive. USB is the existing bench contract; wireless
hardware and its transport remain undecided.

See [protocol](../../docs/CONTROL_INTERFACE.md) for framing and status semantics,
and [firmware](../../firmware/README.md) for build instructions and C++ tests.
`SPEED,25` maps to duty 64/255, identically on mock and MCU. CRUISE/SLOW remain
supported by firmware for existing senders. No speed feedback is available.

## Information needed before motor output

- Exact board/variant, logic voltage, USB behavior and supported PWM pins.
- Driver model, channel layout, enable polarity, brake/coast truth table and limits.
- Actual motor count, wiring/polarity, voltage and combined stall current per channel.
- Battery voltage/current, protection, regulator, grounding and motor-power disconnect.
- Approved pin map and a reviewed local arm/reset interlock.
- Whether wireless is needed; module/interface, range and disconnect behavior.
- Forward-facing Logitech mount, USB tether routing and measured end-to-end latency.

Configure baud/timeout/illustrative presets in firmware `Config.h`. Preserve the
dry-run compile gate until a driver-specific backend has been reviewed. No pins,
wireless modules or active-braking capabilities have been selected here. Existing
four-motor intent is a repository assumption to confirm, not a wiring assignment.
Validate one motor with wheels raised, link loss, reset, stop latch and recovery
before lane tests; then measure actual speed, coast/brake distance and drift.

## Verification for this change

- Python 3.13: six unittest cases passed; package compilation passed.
- Updated sketch: object compilation passed with AVR GCC 7.3.0, Arduino AVR
  core 1.8.8, ATmega328P/Uno compatibility target, warnings treated as errors.
  This was not a full linked board build or upload, and does not select the board.
- C++ host tests were extended for SPEED parsing, duty, timeout and latching;
  not executed locally because no native C++ compiler was available on PATH.
- Existing preview CLI smoke check could not run: Python 3.13 lacks `cv2`.
  No camera/perception code or dependencies were changed.
- No physical hardware, COM-port session, wireless or braking test performed.

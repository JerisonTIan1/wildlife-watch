# USB motor-control protocol V1

The microcontroller endpoint is implemented in **dry-run mode only**. The laptop perception sender and live H-bridge output are not implemented.

## Transport and framing

- USB serial, 115200 baud.
- ASCII, newline terminated; CRLF also accepted.
- Maximum 47 bytes before newline (including an optional CR).
- No spaces, extra fields, signed numbers, or unknown commands. SPEED alone has
  one required percentage field.
- Motion sender target: one fresh command every 100 ms.
- Controller timeout: 500 ms in ARMED, CRUISE, SLOW, or DRIVE.
- These timings are bench defaults; validate against physical stopping measurements.

```text
V1,<sequence>,<command>\n
```

Sequence is an unsigned decimal integer from 1 through 4294967295 and must strictly increase throughout the MCU boot session, including across DISARM/ARM. Repeats, decreases, zero, and overflow fault. Exhaustion requires a deliberate reset while disarmed; do not wrap while operating.

## Commands

| Command | Result |
| --- | --- |
| ARM | DISARMED -> ARMED; no drive; starts watchdog |
| CRUISE | ARMED/CRUISE/SLOW -> CRUISE |
| SLOW | ARMED/CRUISE/SLOW -> SLOW |
| SPEED,percent | Armed states -> DRIVE; integer 1..100 forward duty percentage |
| SPEED,0 | Same latched brake request as BRAKE |
| BRAKE | BRAKE_LATCHED; brake intent immediately |
| FAULT | FAULT_LATCHED; brake intent immediately |
| DISARM | DISARMED; disabled intent |

A valid CRUISE/SLOW outside armed states cannot start motion or clear a latch. ARM outside DISARMED faults. To leave BRAKE/FAULT, the operator must deliberately DISARM, ARM, then request motion. Never auto-run that recovery from the perception loop.

SPEED follows the same arming/latch rules; DRIVE is an armed state and accepts
CRUISE/SLOW too. Percent is 1-3 ASCII digits, 0..100; no fractions or signs.
Example: `V1,2,SPEED,25` requests duty `(25 * 255 + 50) / 100 = 64` using integer
division. Percent represents forward motor duty, not measured vehicle speed.
Existing V1 commands retain their behavior. Older firmware without SPEED will
fault on it; deploy matching firmware before using the new encoder.

Bad records fault without renewing the watchdog. Oversized/damaged records are discarded through their terminating newline so their suffix cannot execute. Blank lines do not renew the watchdog. Timeout is checked before a late command is processed.

## Status

```text
V1,<last_parsed_sequence>,<state>,<reason>,<requested_duty>,SIM\n
```

Example: `V1,2,SLOW,COMMAND,65,SIM`.
Percentage-command example: `V1,2,DRIVE,COMMAND,64,SIM`.

The sequence is the last valid parsed record, even if the requested drive transition was denied. Read state/reason to determine the outcome. Malformed records do not consume a sequence. Status is best-effort and can coalesce to the latest state when transmission is busy; it is not a guaranteed per-command acknowledgement.

SIM explicitly means no motor pins are driven. Duty is the illustrative request for each of the four motors, not measured speed. A brake/fault state is a brake request, not proof of physical stopping.

## Laptop responsibilities

Do not keep sending CRUISE/SLOW from stale images or a failed model. Send FAULT on known failures; stopped transmission also causes the controller watchdog to fault. Use range/path uncertainty conservatively. Perception confidence is not a motor setting.

Require deliberate operator arming and fresh perception. SLOW-to-CRUISE clearance hysteresis belongs on the laptop and is not implemented in this sketch. Never auto-replay ARM or auto-rearm after reconnect/reset. Sequences are not authentication and reset on MCU reboot; a real backend requires a reviewed local arm/reset interlock.

Use manual commands before perception integration. First test boot, timeout, duplicate/bad input, brake latch, and explicit recovery without motor power. Measure the actual driver behavior before enabling live outputs.

Python mock and byte encoder: [hardware setup](../wildlife_watch/hardware/README.md).
The encoder is not yet a connected, status-monitoring serial controller.

# Laptop-to-controller contract (proposal)

**Design draft: neither endpoint is implemented.** Agree on this before coding.

The laptop owns fresh camera input, detection, position/range/uncertainty, path relevance, and risk decisions. The Uno/Nano/ESP32 owns motor outputs, arming, watchdog, and fault response. Communication is USB serial.

## Proposed messages

Newline-terminated ASCII supports early testing from a serial terminal:

```text
V1,<sequence>,<mode>\n
```

Modes: CRUISE, SLOW, BRAKE, FAULT. Sequence is an increasing unsigned integer within an armed session. For example, send `V1,12,SLOW` followed by a newline.

The controller uses local, tested drive settings; the laptop does not need to send PWM or distance to the motor layer. Log range and decision evidence on the laptop.

Proposed status response:

```text
V1,<sequence>,<controller_state>,<reason>\n
```

Acknowledgement means the controller accepted the request and requested outputs. It does not prove physical stopping. Do not label the reply STOPPED without a defined measurement.

Baud rate, send cadence, command timeout, maximum line size, and the arm mechanism remain to be finalized.

## State and freshness rules

- Boot DISARMED with no forward output. Arming is deliberate and separate from normal risk messages.
- Clear buffers and establish a fresh agreed sequence baseline for each armed session. Reject duplicate/out-of-order messages; stop/re-arm before sequence wrap.
- Only valid, fresh, increasing-sequence messages renew the command watchdog. Invalid or oversized input must not create motion; use bounded nonblocking parsing and a fault response.
- BRAKE bypasses normal speed ramps, requests the tested brake output promptly, and latches the stop.
- FAULT and command timeout latch a stop. Reset/reconnect cannot resume forward motion automatically.
- The laptop must not renew motion commands from stale frames. A live serial connection does not establish camera/model health.
- SLOW can return to CRUISE only after stable fresh clearance under a tested hysteresis rule.
- BRAKE/FAULT require operator re-arm after clearance or repair.
- Power loss may remove active braking; document actual physical behavior.

First test manual modes, replies, bad input, timeout, USB unplug, and reset with wheels raised. Then integrate perception. Select watchdog timing against the measured stopping budget.

# Motor-controller firmware - Jerison

**Version 1 is a dry run. It parses real USB serial commands and computes four motor output requests, but it never configures or drives motor pins.**

This lets you work on control logic before the exact H-bridge, board, motor ratings, and power supply are known. Changing the dry-run flag to zero deliberately fails compilation: the live driver backend is not implemented.

## Open it

Open `WildlifeMotorController/WildlifeMotorController.ino` in Arduino IDE. Keep Config.h, Controller.h, and DryRunMotorDriver.h in the same sketch folder.

Verified compilation: Arduino Uno and classic ATmega328P Nano using Arduino AVR core 1.8.8. ESP32 has not been compiled/tested. Nano Every and other Nano variants are different targets.

With motor power disconnected, select your actual board/port and upload the dry-run sketch when ready. No upload was performed during repository setup.

## What each file does

| File | Purpose |
| --- | --- |
| WildlifeMotorController.ino | USB input, frequent watchdog checks, and nonblocking status output |
| Controller.h | Parser, arming, sequence checking, state machine, and four-motor intent |
| Config.h | 115200 baud, 500 ms timeout, and illustrative PWM request values |
| DryRunMotorDriver.h | Stores requests in memory; no GPIO operations |
| ../tests/controller_test.cpp | Host tests of behavior and failure cases |

All four requested duty values are equal in this version. CRUISE requests 120/255; SLOW requests 65/255. These are illustrative values, not measured speed targets or approved live settings. BRAKE is a distinct output intent, not just duty zero.

## Serial Monitor first test

Set **115200 baud** and **Newline** (or Both NL & CR). Opening USB may reset an Uno/Nano.

Send:

```text
V1,1,ARM
```

Expected latest status:

```text
V1,1,ARMED,OPERATOR,0,SIM
```

After 500 ms without another valid command, expect:

```text
V1,1,FAULT_LATCHED,TIMEOUT,0,SIM
```

That timeout is intentional. ARM does not move the car, and it does not disable the watchdog.

To recover, send `V1,2,DISARM`. The next deliberate arm would be `V1,3,ARM`. Sequence numbers must keep increasing until a board reset; disarming does not reset them.

To exercise SLOW/CRUISE, a terminal or sender must transmit ARM followed by the drive command within 500 ms. For example, send these two newline-terminated records together after a fresh board reset:

```text
V1,1,ARM
V1,2,SLOW
```

Expect SLOW with requested duty 65, then TIMEOUT when no fresh commands arrive. Do not disable the watchdog just to make manual typing easier.

A future laptop sender should send new sequence numbers every 100 ms only while perception is healthy and fresh. That cadence and the 500 ms timeout are bench starting values, not validated stopping parameters.

## Commands

| Command | Meaning |
| --- | --- |
| ARM | Only valid from DISARMED; enters ARMED without drive |
| CRUISE | Requests forward cruise duty if armed |
| SLOW | Requests reduced forward duty if armed |
| BRAKE | Requests braking and latches the stop |
| FAULT | Requests a fault stop and latches it |
| DISARM | Disables drive and permits a later explicit ARM |

BRAKE/FAULT cannot be released by CRUISE or SLOW. Recovery requires DISARM, ARM, then a fresh drive command. DISARM requests disabled outputs; on actual hardware this may coast. Do not disarm a moving vehicle as a substitute for a validated brake action.

Malformed input, old/duplicate sequence numbers, and timeout fault the controller. Partial frames and blank lines do not keep it alive. The sketch avoids blocking reads, delays, and dynamic String allocation.

Statuses are best-effort latest-state reports and may coalesce under heavy traffic. They report requested behavior, not physical speed/stopping. A status sequence is the last valid parsed sequence, not a promise that motion was accepted. Read the state and reason.

## Run logic tests

From the repository root with a C++ compiler:

```sh
g++ -std=c++11 -Wall -Wextra -Werror -pedantic firmware/tests/controller_test.cpp -o controller_test
./controller_test
```

On Windows choose an .exe output and run it from PowerShell. CI also runs these tests.

Tests cover boot/disarmed output, all four duty requests, arming/recovery, latched brake/fault, timeout boundaries, millis rollover, repeated sequence numbers, malformed/oversized/fragmented input, and sequence overflow. Uno and classic Nano compile checks used 4760 bytes flash and 465 bytes global RAM. None of these prove physical braking.

## Next hardware step

Identify the exact H-bridge module, controller board, motor voltage/stall current, and battery. Then implement a driver-specific backend with correct pin mapping, polarity, current limits, coast/brake truth table, boot outputs, and operator arming.

The live backend must implement four-wheel intent using the actual number of driver channels; four motors does not automatically imply four independent channels. Test one motor first with wheels raised, then all four.

Serial ARM/DISARM is a prototype operator convention, not authentication. Sequence numbers reset on board reboot and do not protect against a sender replaying an entire ARM/drive stream after reset. Live operation therefore requires a reviewed local arm/reset interlock and host reconnect behavior.

Timing follows Arduino's nonblocking millis pattern. [Arduino Blink Without Delay](https://docs.arduino.cc/built-in-examples/digital/BlinkWithoutDelay/) explains the underlying approach.

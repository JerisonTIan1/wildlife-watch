# Motor firmware - Jerison

Reserved for the controller code. No sketch is implemented yet: the H-bridge model, board, motor ratings, and supply remain undecided.

## Deliverables

1. Wiring/pin table tied to actual hardware, logic levels, power paths, and motor polarity.
2. Driver-specific forward, brake, coast/disable, and fault-output helpers.
3. Nonblocking DISARMED / CRUISE / SLOW / BRAKE_LATCHED / FAULT_LATCHED state machine.
4. Bounded USB parser and status replies under the agreed [control contract](../docs/CONTROL_INTERFACE.md).
5. Command watchdog, deliberate arm/re-arm, safe boot/reset outputs, and brake priority.
6. One-motor, four-motor, disconnect, and physical stopping measurements.

Keep pin definitions and tested drive settings in one board-specific configuration. Keep perception on the laptop. Use manual commands first so firmware work is not blocked by the detector.

Do not invent a generic H-bridge truth table. Validate the selected module's brake/coast behavior before finalizing pin-driving functions.

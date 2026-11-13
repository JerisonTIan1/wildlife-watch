# Team backlog

## P0 - hardware and interfaces

- [ ] Jerison: identify H-bridge, motor voltage/stall current, battery, and exact controller board.
- [ ] Whole team: agree on CONTROL_INTERFACE.md, timeout, stop/re-arm behavior, and status fields.
- [ ] Mechanical owner: confirm component dimensions, mounts, wiring access, and camera geometry.
- [ ] Perception owner: confirm camera formats, simultaneous capture, and a testable distance method.

## P1 - work independently

- [ ] Jerison: demonstrate one-motor forward/slow/brake behavior with wheels raised.
- [ ] Jerison: expand to four motors and verify polarity, driver capacity, and physical power disconnect.
- [ ] Jerison: implement bounded USB parser, state machine, acknowledgement, watchdog, and latched stops.
- [ ] Mechanical owner: print/assemble chassis and measure alignment, drift, and mount stability.
- [ ] Perception owner: implement detector and explicit unknown-obstacle handling.
- [ ] Perception owner: validate position, distance/uncertainty, path relevance, and severity outputs.
- [ ] Perception owner: implement USB sender that faults on stale perception.

## P2 - integrate and measure

- [ ] Exchange manual USB commands before connecting the detector.
- [ ] Measure speed, end-to-end latency, braking/coast distance, and lane drift.
- [ ] Select slow/brake thresholds from measurements.
- [ ] Demonstrate clear, far in-path, immediate in-path, and side-of-lane targets.
- [ ] Demonstrate unplug, stale frames, bad input, reset, and deliberate re-arm.
- [ ] Record a repeatable demo and label any proxy targets.
- [ ] Itemize cost and state the limits of RC-scale results.

No steering, reverse travel, full-size-car integration, mobile app, or custom PCB is required.

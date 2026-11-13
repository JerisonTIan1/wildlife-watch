# Team backlog

Turn each task into an issue, select one owner, and link its PR. Choose owners as a team.

## P0 - unblock integration

- [ ] Inventory camera models, thermal interface, compute, currency, and $700 estimate contents. Done: hardware document contains verified entries.
- [ ] Confirm repeatable RGB capture. Done: Logitech feed runs and failure behavior is recorded.
- [ ] Implement thermal adapter if required. Done: real camera frames are available with documented format and timing.
- [ ] Agree on event schema and module boundaries. Done: detector and UI can exchange a sample event without embedding model code in the UI.

## P1 - working wildlife demonstration

- [ ] Choose target species and assemble permissioned, labeled positive and negative recordings.
- [ ] Implement RGB detector. Done: model/classes/license are documented and baseline results exist on held-out recordings.
- [ ] Implement visual warning and fault states. Done: candidate, monitoring, stale, and disconnected states are demonstrated.
- [ ] Integrate thermal evidence. Done: added benefit or lack of benefit is measured using the same evaluation split; calibration limitations are documented.

## P2 - credible presentation

- [ ] Complete reproducible bill of materials and distinguish borrowed hardware from cash spent.
- [ ] Record a repeatable demo with successful and failed detections.
- [ ] Report recall, false alerts, latency, FPS, and test conditions.
- [ ] Agree on a license and whether to make the repository public.

Defer autonomous control, braking, custom PCBs, mobile apps, cloud services, and unvalidated distance estimates until the core demo works.

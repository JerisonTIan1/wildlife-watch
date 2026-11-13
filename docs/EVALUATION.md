# Evaluation: perception to physical stop

Current evidence: synthetic-video preview checks, host tests of the motor-controller parser/state machine, and Uno/classic Nano sketch compilation. **No live motor output, range estimation, or physical automatic stopping has been validated.**

## Motor control - Jerison

Begin with one motor, then four with wheels raised. Verify direction, forward/slow/brake modes, reset/arming, acknowledgements, timeout, and stop priority. Test the actual H-bridge brake and coast modes separately.

In a bounded low-speed lane, measure speed, drift, brake-command-to-stop distance, and coast distance. Record surface, battery state, mass, PWM setting, and repeated trials. PWM is not a measured speed.

## Perception and ranging - teammates

Define species, recording permissions, and unknown-obstacle handling. Split model evaluation by recording session. Report encounter recall, precision, false detections per minute, and misses under stated conditions.

Compare estimated range with measured target locations. Report error and invalid estimates; distinguish camera distance from front-bumper clearance. Verify travel-corridor overlap with allowance for chassis width and observed drift.

Compare RGB-only and combined modes on the same scenes. Document timing and sensor disagreement. Two displayed feeds do not establish fusion or depth.

## End-to-end acceptance

| Scenario | Required observation |
| --- | --- |
| Healthy clear lane after operator arm | Forward travel at tested setting |
| Farther in-path target | Measurable slowing before brake zone |
| Immediate in-path target | Prompt brake request and measured physical stopping |
| Side-of-lane target | Distinguished from in-path threat under the agreed policy |
| USB loss, stale frames, or model failure | Fault stop; last forward command is not held indefinitely |
| Bad/replayed input or controller reset | No unintended movement or automatic restart |

Measure capture-to-decision, communication/firmware delay, and physical stopping separately. Do not subtract independent laptop/controller clocks without synchronization.

A planning expression is `required_distance = speed * total_delay + measured_braking_distance + margin`, with consistent units. Use measured RC values, conservative observed delay, and a margin for range error/test variation. Set a farther slow threshold and hysteresis. This is not a road-vehicle stopping guarantee.

Label model animals, printed images, mock detections, and warm proxies as staged inputs. They can test geometry/control without validating real deer recognition.

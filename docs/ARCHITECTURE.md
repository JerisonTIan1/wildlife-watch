# Architecture and MVP boundaries

## Confirmed direction

- Vehicle-mounted Logitech webcam on top of the vehicle.
- Thermal camera available; exact model, mounting, and interface to confirm.
- Wildlife awareness and an eventual driver warning interface.
- No drone, autonomous driving, steering, or braking control.

## Planned pipeline

```text
Logitech RGB -> capture -> wildlife detector -------+
                                                   +-> temporal checks -> warning UI
Thermal     -> adapter -> thermal evidence ---------+
                         calibration/association
```

Only the preview capture utility exists today. The rest of this diagram is a proposed architecture.

Begin with RGB-only detection and a separate thermal preview. Select a model only after checking that its classes and training data cover the target animals. Do not map unknown animals into unrelated labels just to make the demonstration appear successful.

For thermal integration, first establish whether the device provides video, raw sensor values, or calibrated temperatures. A false-color stream is not automatically temperature data. Keep the thermal view separate until timestamps, fields of view, and calibration support association. A side-by-side view is not sensor fusion.

A roof mount can move and vibrate. Record camera intrinsics, relative pose, and a repeatable alignment check before associating observations. Do not assume a single flat-ground transform aligns animals at all distances.

## Warning states to implement

- **Starting / unavailable:** capture or model not ready.
- **Monitoring:** frames are arriving; this does not mean the road is clear.
- **Wildlife candidate:** detector evidence requires attention; display source and age.
- **Sensor fault / stale data:** explicitly show missing or old frames; suppress stale detections.

Use persistence and cooldown rules to limit flicker, then evaluate their latency cost. Begin with a visual indicator. Distance, collision probability, and time-to-collision must not appear as measured values without a validated estimator.

## First demo

1. Start the preview with known inputs and verify both sources.
2. Show a labeled wildlife recording with an RGB baseline.
3. Compare the same evaluation scenarios with thermal evidence enabled.
4. Show an empty scene and a sensor disconnection, not just successful detections.
5. Present measured results and the itemized prototype cost.

Controlled substitutes may test UI behavior, but a person, toy, or warm object does not validate wildlife detection.

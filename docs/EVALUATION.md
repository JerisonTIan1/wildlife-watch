# Evaluation plan

The question is whether thermal evidence improves wildlife warnings over RGB alone, at a useful range and latency. A good-looking bounding box does not answer that.

## Before measuring

Choose target species and define an encounter, an alert match window, and the observation region. List footage provenance and usage permission. Label positive encounters and animal-free negative scenes. Split evaluation by recording/session so adjacent frames do not leak between training and evaluation. Keep the same held-out clips and thresholds for the final comparison.

## Compare

| Mode | Purpose |
| --- | --- |
| RGB only | Establish baseline |
| Thermal only, if supported by an appropriate model | Understand thermal capability |
| Combined | Test added value against baseline |

Report daylight/low-light conditions, occlusion, target species, approximate distance only when measured, and stationary/moving setup separately. Do not invent range from image size.

## Report

- Encounter recall: detected labeled animal encounters / total labeled animal encounters.
- Alert precision: true matched wildlife alerts / all alerts, using a written matching rule.
- False alerts per minute of negative footage, including warm non-animal objects.
- Capture-to-alert latency (median and p95), using a documented clock and timestamp method.
- Processing FPS, dropped/stale frames, and compute hardware.
- First alert distance only if independently measured; otherwise report unknown.
- Number of independent recordings and encounters, with failure examples.

Current results: **not measured**. Synthetic clips verify software plumbing only. Sequential OpenCV reads do not provide sensor exposure synchronization or end-to-end capture latency.

## Required failure demos

Show a disconnected camera, an ended video, an occluded animal, an empty scene, and a warm non-animal object. The UI must never display "safe" merely because detections are absent. Start with stationary or controlled data collection; this prototype is not a basis for relying on warnings during public-road driving.

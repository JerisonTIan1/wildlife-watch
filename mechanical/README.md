# Mechanical models

| Model | Files | Dimensions |
|---|---|---|
| [Wildlife Watch car V3](car/v3/) | Editable SOLIDWORKS 2025 assembly and 17 linked parts | 243 x 172 x 59.5 mm overall, excluding webcam |
| [Reindeer target](reindeer/) | 3MF mesh with creator attribution | 185.708 x 175.149 x 240 mm |

The current car design is **two-motor front-wheel drive**, with two passive rear wheels on a printed through-axle. This supersedes the early four-motor chassis proposal. Firmware and electrical documents may still describe the earlier four-motor interface; this CAD upload does not change firmware.

Open the car assembly with its `parts/` folder alongside it. The car contains editable sketches/features; the downloaded reindeer is a mesh and has no native CAD feature history. No STL files are added here.

The car includes nominal Nano, breadboard, motor and ToF reference envelopes plus reserved driver/battery space. Actual hardware dimensions and motor shaft fit remain unverified. A thermal-camera mount is not modeled. See each model's README before manufacturing.

For the two-printer deadline plan, omit the car's decorative roof and four wheel arches. Keep its lid and running gear. Your print operator must confirm slicer estimates; six hours is a target, not a verified duration.

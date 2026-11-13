# RC hardware and cost

Pitch: **a low-cost wildlife-aware RC demonstrator with automatic slowdown and braking**.

The preliminary team estimate is roughly $700 including the thermal camera. Currency and included components need itemization. This is not a verified full-size automotive product price.

| Component | Confirmed | Still needed |
| --- | --- | --- |
| Chassis | To be 3D printed | CAD, dimensions, material, print settings |
| Motors | Four DC motors | Part numbers, rated voltage, no-load/stall current, gearbox |
| Driver | H-bridge type | Exact module, channels, ratings, brake truth table |
| Controller | Uno, Nano, or ESP32 under consideration | Exact board, logic voltage, PWM/USB capabilities |
| Battery/power | Undecided | Voltage, current capacity, protection, connectors, regulation |
| RGB | Logitech webcam on top | Model, frame rate, mount |
| Thermal | Available | Model, interface, data format, frame rate, FOV |
| Compute/link | Laptop connected by USB | OS, camera connections, performance, cost inclusion |
| Operator stop | To implement | Physical motor-power disconnect and software stop |

## Before wiring

1. Identify the actual H-bridge before selecting pins or brake logic. Its truth table is module-specific.
2. Size each channel and the power path for its load, including startup/stall conditions. If motors share a channel, account for combined load.
3. Supply motors through the driver, not controller GPIO. Verify logic compatibility, power routing, grounding, protection, and decoupling using selected hardware documentation.
4. Define boot/reset outputs so power-up or opening USB cannot start the car.
5. Establish brake versus coast behavior, permitted braking duration, and current/thermal limits.

Brake and coast are distinct bridge states; TI's DRV8251 documents both. This is an example reference, not a selected/recommended part for the unknown motors. [TI datasheet: Device Functional Modes](https://www.ti.com/lit/ds/symlink/drv8251.pdf).

A physical motor-power disconnect is an independent fallback, but removing power may cause coasting rather than active braking. Document the actual behavior.

## Measurements

Record wheel direction, speed, lane drift, braking/coasting distance, startup current behavior, driver temperature, and controller resets. Left/right motor mounting may require opposite electrical polarity for forward travel. Account for the USB tether.

Record cash spent and replacement cost separately. Include prints, wheels, fasteners, motors, driver/controller, power, cameras, mounts, and cables; state whether the laptop is included.

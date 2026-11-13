# Hardware and cost

Working description: **low-cost vehicle-mounted wildlife warning prototype**.

The team estimates approximately **$700 including the thermal camera**. Currency and included components are not yet confirmed. Do not present this as a complete retail price or publish a savings percentage.

| Item | Known information | Confirm / price |
| --- | --- | --- |
| RGB camera | Logitech webcam on top of vehicle | Exact model, resolution, FPS, mount, cost |
| Thermal camera | Available; included in approximate $700 estimate | Model, interface, resolution, FPS, lens/FOV, cost |
| Compute | Not specified | Laptop/board, power draw, whether included in $700 |
| Mounts and enclosure | Not specified | Vibration resistance, weather protection, placement, cost |
| Power and cables | Not specified | Supply, adapters, cable lengths, cost |
| Warning interface | To implement | Existing display or additional device, cost |
| Taxes/shipping | Unknown | Include/exclude explicitly |
| Currency | Unconfirmed | Confirm before any priced pitch |

Record both **cash spent for this demo** and **replacement cost for another team to reproduce it**. Borrowed hardware is not free in a reproducible system cost. Keep receipts or dated source links with the final bill of materials.

## First hardware checks

- Write down device models and supported operating systems.
- Confirm the thermal camera exposes UVC video or needs a manufacturer SDK.
- Check the intended thermal optical path and mounting against manufacturer documentation.
- Capture the actual resolution, frame rate, orientation, and field of view of each camera.
- Verify simultaneous capture, USB bandwidth, timestamp behavior, and power stability.
- Test mount stability in a controlled setting before collecting moving-vehicle data.

Pitch wording: "A low-cost prototype that pairs a vehicle-mounted webcam with thermal imaging to investigate earlier wildlife warnings. Our preliminary hardware estimate is about $700, including the thermal camera; detection performance and full reproducible cost are being measured."

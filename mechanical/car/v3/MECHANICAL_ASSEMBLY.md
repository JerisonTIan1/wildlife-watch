# Mechanical assembly for the V3 exterior

The V2 drivetrain and component reference envelopes are retained. Use README.md for the new exterior dimensions and trim attachment.

## Rear axle assembly

1. Print the coupon, one rear wheel and one spacer first. With the coupon notch at bottom left, hole diameters left to right are **1.8, 1.9, 2.0, 2.1, 2.2, 2.3, 3.2, 3.4, 8.2, 8.4, 8.6 mm**. Check the 8.4 mm hole and actual wheel bore against the printed axle. Remove roughness without making the fit sloppy.
2. Slide the long axle through both chassis support channels, with its flat face downward. Center it so each end projects 18 mm beyond the chassis side wall. Secure the axle in both supports with a PLA-compatible adhesive; let it cure. The shaft should stay still while the wheels spin.
3. On each end, slide on a 1 mm spacer, then a rear wheel. In the modeled position the spacer occupies Y = 65–66 mm, wheel 67–77 mm, and cap 78–86 mm, mirrored on the opposite side. There is 2 mm total axial space between the spacer and cap for the 10 mm wheel. The loose wheel may settle to either side of that space.
4. Fit each end cap with its socket facing inward. The cap's inner face should be 13 mm beyond the chassis wall, leaving 5 mm shaft engagement. **Do not push the cap against the wheel.** Confirm free spinning, then bond only the cap socket to the shaft tip. Keep adhesive out of the wheel bore and away from the wheel faces. These are adhesive-retained caps, not snap-fit or threaded fasteners.
5. Check both wheels spin independently without rubbing the body or caps. Run an initial low-speed, loaded test to check axle deflection, wear, cap retention and rolling resistance. This is a PLA prototype axle, not a validated replacement for a metal shaft at every load.

No metal axle, rear nuts or rear bolts are required for this revision. Screws for the lid and ToF mount, front motor ties, and electronics attachment are still separate hardware.

The axle clears the modeled breadboard by 6 mm in X and the Nano planning block by 1 mm in X. **Route the Nano USB cable over the axle through the upper part of the rear opening.** The shaft top is Z = 17.5 mm and the rear opening extends to Z = 30 mm. Actual plug size and cable bend clearance remain unmeasured. The existing 24 × 22 mm USB opening, adjustable ToF mount remain. The webcam tapes to the V3 roof panel.

Component envelopes remain references: motor 27.5 × 20 × 15 mm with Ø2 × 8 mm shaft; breadboard 170 × 55 × 10; Nano including assumed headers 50 × 22 × 16; ToF board 18 × 13 × 2. Reserved battery space is 70 × 28 × 20 and driver space 45 × 28 × 15. Those are not confirmed dimensions of your hardware. No thermal camera mount is included. Front motor torque, wheel attachment and straight-line control still require testing; a small bare motor may need gear reduction.

The motor geometry comes from a [130-size mechanical reference](https://www.adafruit.com/product/711), not identification of your motor or a voltage recommendation. Other references: [Nano](https://docs.arduino.cc/hardware/nano/), [breadboard](https://www.adafruit.com/product/239), [ToF carrier](https://www.pololu.com/product/2490), [K2 printer series](https://www.creality.com/products/k2-series-3d-printer).


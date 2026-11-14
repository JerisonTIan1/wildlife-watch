# Wildlife Watch V3 — rover exterior

V3 gives the car faceted body corners, shaped front/rear bumpers, four dark wheel-arch trims and a sloped roof panel with a flat webcam surface. The two-motor front drive, printed rear axle and component planning positions are retained from V2.

Open `WildlifeWatch_Rover_V3.SLDASM` in SOLIDWORKS 2025, keeping the `parts` folder beside it. Hide both `Flat_Webcam_Lid_V3` and `Sloped_Webcam_Roof_V3` to inspect the interior. Parts have native editable sketches and extrusion features. The assembly is a fixed-position layout, not a motion simulation.

## Size

| Measurement | Millimetres | Centimetres |
|---|---:|---:|
| Overall length × width × height, excluding webcam | **243 × 172 × 59.5** | **24.3 × 17.2 × 5.95** |
| Main chassis print, including bumpers | 234 × 130 × 40 | 23.4 × 13.0 × 4.0 |
| Lid footprint | 220 × 130 | 22.0 × 13.0 |
| Ground clearance below floor | 11.5 | 1.15 |
| Wheel diameter | 50 | 5.0 |
| Wheelbase | 165 | 16.5 |
| Printed rear axle length | 166 | 16.6 |

Overall length includes the rear arch trim; width includes the axle end caps; height runs from wheel contact level to the roof. The webcam, cables and an additional camera are excluded. These are nominal CAD dimensions, not measurements of physical prints. `overall_dimensions.csv` records the native solid-body extrema used to check the assembled dimensions.

## Print list

This repository stores editable SolidWorks source only, as requested. Export the required parts to STL or 3MF locally for printing; keep millimetres at 100% scale. The quantities below refer to part names.

| Part base name | Qty |
|---|---:|
| Chassis_FWD | 1 |
| Flat_Webcam_Lid | 1 |
| Sloped_Webcam_Roof | 1 |
| Wheel_Arch_Trim | 4 |
| Front_Wheel_2mm_REFERENCE | 2 |
| Rear_Wheel_8p4mm_PrintedAxle | 2 |
| Rear_Through_Axle_8mm_166L | 1 |
| Rear_Axle_Spacer_1mm | 2 |
| Rear_Axle_End_Cap | 2 |
| Adjustable_ToF_Plate | 1 |
| Shaft_and_Axle_Fit_Coupon | 1 |

Eleven unique printable part designs and eighteen printed pieces including the coupon. All individual parts fit the Creality K2 Plus build envelope. No slicer project or validated single-plate arrangement is supplied. Reference blocks in `parts` are not printable electronics or hardware.

Print the chassis floor-down; lid broad outside face down with tabs up; roof broad base down; arches and sensor plate flat; wheels web-side down. Rotate the 166 mm axle onto its long flat face in the slicer rather than printing it vertically. Print caps with sockets up. Use solid infill for axle and caps. A starting chassis profile is 0.20 mm layers, four walls and 20–30% infill; use your PLA manufacturer's temperatures and inspect support previews at the horizontal chassis openings. Physical prints remain unvalidated.

## Exterior attachment

The roof is a separate printed part bonded to the removable lid. Its base is 160 × 100 mm, height 6 mm, with 45-degree slopes and a 148 × 88 mm top envelope with clipped corners. Center it across the width, with its rear edge 20 mm forward of the lid's rear edge: base spans X = -90 to +70 and Y = -50 to +50 mm. Keep the lid screw holes accessible. Tape the webcam to the flat top after checking the actual camera base fits.

Each arch trim is 3 mm thick, with outer radius 30 mm and inner radius 27 mm. Bond to the outside chassis side wall, centered on the wheel shaft: front X = +70 mm, rear X = -95 mm, center Z = 13.5 mm. The 50 mm wheels have 2 mm nominal radial clearance to the trim. The arch tips sit 3 mm above the chassis floor datum. Check alignment and spinning clearance before adhesive cures. These are cosmetic trims, not tested impact guards.

The body and lid use 8 mm corner chamfers. The bumpers are integral to the chassis. The CAD colors show a blue body and dark roof/arches; print those separate parts in your chosen filament colors. No multicolor toolpaths are included.

Use the V3 body and lid as a matching set. Motor saddles, rear axle supports, sensor/cable openings and electronics reference positions retain their V2 locations. See `MECHANICAL_ASSEMBLY.md` for the printed rear axle assembly and component assumptions.

## Validation

`geometry_checks.csv` records native single-solid checks and dimensions; `interferences.csv` and `assembly_positions.csv` record the assembled collision audit. Passing CAD checks does not establish physical fit, strength, rolling resistance or motor performance. The actual motor, Nano headers, breadboard, H-bridge and battery remain unmeasured. The thermal camera is not modeled.

The generator and verification scripts are in `source`. A full build overwrites generated V3 files; keep manual changes separately before regenerating. `-Resume` reuses existing parts and does not update their geometry. The saved files were generated using SOLIDWORKS 2025 Student Edition.

## Team file handling

Download the whole `v3` folder (or the repository ZIP); keep `parts/` next to the assembly. Open the `.SLDASM` in SOLIDWORKS 2025 or a compatible newer version. If SolidWorks asks to locate a component, browse to the matching file in `parts/`; the original machine path may be cached. Do not upload temporary `~$` lock files. Coordinate edits to a part before starting: Git cannot merge SolidWorks binary files.

For the deadline print, omit the sloped roof and four wheel arches; retain the flat lid and all running gear. That is 12 production pieces, plus the fit coupon. The original full exterior design remains in this assembly. No slicer settings or measured print times are provided.

# Deer localization from a rigid marker mount

This opt-in mode estimates a measured body/trolley bounding box from marker ID 0.
It is **marker-assisted geometry**, not animal recognition or an independently
observed silhouette. It reuses calibrated PnP and requires a rigid mount: if the
marker moves relative to the deer, the estimated region becomes wrong.

## Measure the rigid assembly

Use centimeters throughout. Marker coordinates are tied to its printed orientation:
origin at the **outer black square's center**, +X toward its canonical right edge,
+Y toward its canonical top edge, and +Z outward from its printed face toward
the camera when front-on. Camera coordinates remain +X right, +Y down, +Z forward.
The PnP rotation transforms between these frames; do not flip signs manually.

Measure an enclosing rectangular box aligned with those marker axes. Include the
reindeer and trolley/wheels and any rigid support that must count as a collision.
For each marker axis, measure the minimum and maximum occupied coordinates:

- `center_marker_cm = [(xmin+xmax)/2, (ymin+ymax)/2, (zmin+zmax)/2]`
- `size_marker_cm = [xmax-xmin, ymax-ymin, zmax-zmin]`

This accounts for lateral displacement, vertical separation and fore/aft mount
offset. A body below the marker has negative center Y. A body behind the printed
face has negative center Z. Use the **box center**, not a foot, antler, or marker
bottom edge, as the offset reference. Record total dimensions; sizes must all be
positive. If the body is rotated relative to the marker, measure a larger enclosing
box aligned to the marker axes rather than pretending those axes match the body.

Create `runs/deer-geometry.json` with your measurements. This is a schema template,
not runnable geometry; replace every null with a measured number (zero is valid
for an offset, but not a size):

```json
{
  "schema_version": 1,
  "center_marker_cm": [null, null, null],
  "size_marker_cm": [null, null, null]
}
```

No default offsets/dimensions or fabricated measured geometry file is supplied.
Intrinsics and marker side must still be measured as described in
[MARKER_POSE.md](MARKER_POSE.md).

## Run

Append `--target-geometry runs/deer-geometry.json` to your working calibrated
webcam or collision-demo command. Example (replace the camera index and marker
side with your actual values; 7.00 is valid only for a measured 7.00 cm square):

```powershell
.\.venv\Scripts\python.exe -m wildlife_watch.aruco_webcam --camera 1 --backend dshow --width 640 --height 480 --fps 30 --fourcc MJPG --calibration runs/logitech-calibration.json --marker-side-cm 7.00 --target-geometry runs/deer-geometry.json
```

The collision demo passes this option through to the same webcam pipeline. Keep
the existing mock backend and configuration gates; this feature introduces no
new hardware path. Without the option, existing marker-centered behavior remains.

The green rectangle says **DEER - MARKER ASSISTED**. ArUco corners/center remain
visible by default. Add `--hide-marker-outline` for presentation: only the raw
corner/center graphics disappear, not marker detection, ID status or diagnostics.

## Geometry and downstream contract

PnP exports its existing `rvec` and `tvec` without changing the solver/calibration.
For each measured body point `p_marker`, compute
`p_camera = R_marker_to_camera * p_marker + t_marker_to_camera`.
OpenCV `projectPoints` projects all eight box vertices using the real intrinsics
and distortion. A clipped image-axis rectangle encloses their projected pixels.
This is an approximate box, not segmentation: it includes background, may be
loose at oblique angles, and distorted edges need not attain extrema at vertices.

In this mode the existing Observation schema is extended compatibly:

- `position_reference="deer_body"`; `distance_cm` and `lateral_cm` refer to the
  transformed **body-box center**, not the marker.
- `closing_speed_cm_s` is freshly estimated from body-center Z with the existing
  speed-filter class. Marker closing speed is not blindly reused under rotation.
- `target_half_width_cm`, `target_half_depth_cm` are enclosing camera-axis extents
  computed as `abs(R) * half_size`. Collision prediction uses these instead of the
  static marker-centered target dimensions in collision config. Vehicle dimensions
  and safety margin still apply. Missing body extents produce UNKNOWN.
- `marker_rvec` and `marker_tvec_cm` explicitly remain the **raw marker pose** for
  debugging; they are not body translation. Defaults are None for compatibility
  with prior callers. `position_reference` defaults to `marker` for prior callers.

All eight corners must be in front of the camera. Invalid marker pose, ambiguous
or missing marker, incompatible resolution or invalid projection produces no body
box and no current body position/speed. Speed history resets on loss. If the body
is entirely offscreen while the marker is valid, no rectangle is drawn but the
rigidly inferred body observation may still be valid; it is not a claim that body
pixels were detected. Historical data in the existing loss overlay stays labeled.

Collision prediction still assumes straight driving and constant relative velocity
with current extents held over its horizon; it does not forecast future target
rotation. PnP planar ambiguity can produce orientation jitter, amplified by a long
marker-to-body offset. Measure and test at the actual distances/angles; do not
interpret a plausible-looking green box as proof of accurate localization.

## Validate

At stationary near/mid/far positions, check the region encloses the real assembly.
Move sideways and rotate the trolley moderately; the box should follow perspective
and the measured mount offset. Cover the marker: the box must disappear immediately
and collision input must become invalid/UNKNOWN. On recovery speed must warm up.
Then test the rigid assembly on the moving-car setup, including motion blur.

```powershell
.\.venv\Scripts\python.exe -m unittest wildlife_watch.test_deer_localization -v
```

Tests use synthetic intrinsics and geometry only. They verify offset signs,
projection scale, rotated centers/extents, collision coordinate consistency,
loss/recovery, missing pose and invalid geometry. Physical offsets and box accuracy
have not been measured or validated by the agent.

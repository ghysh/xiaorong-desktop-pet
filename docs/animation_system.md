# Stage 7 animation system

## Goal and preservation rule

Stage 7 introduces a small, testable animation layer without changing the approved character PNG. The runtime master remains `assets/fullbody/final/fullbody_runtime_master.png`; it is validated during initial load and is not read, hashed, resized, or modified per animation frame. No GIF, frame PNG, OpenCV process, image model, mesh deformation, or random input is used.

## Phase-stable behavior transitions

Behavior profile transitions calculate both endpoint transforms from the same monotonic timestamp and then interpolate the final transforms. Breathing-period multipliers are never interpolated before periodic phase calculation. This prevents long uptime from amplifying a small period change into several alternating scale jumps when entering or leaving `RESTING`. Regression coverage samples every automatic-state pair after 60 seconds, 10 minutes, and one hour.

## Structure

- `animation/transform.py` defines immutable `AnimationTransform` values: local offset, scale, and rotation only. It provides validation, comparison, composition, `QTransform` conversion, and transformed Alpha-bound geometry.
- `animation/easing.py` contains deterministic pure `linear`, sine, cubic, and clamp functions with no Qt dependency.
- `animation/idle_motion.py` calculates the three idle components directly from elapsed monotonic time. Its phase offsets and periods differ, so the components do not mechanically synchronize.
- `animation/controller.py` owns exactly one 30 FPS `QTimer` and a `QElapsedTimer`. It emits `transform_changed` and neither owns an asset nor moves a widget.
- `ui/pet_window.py` loads and caches the image once, computes the actual Alpha box and feet pivot, then repaints the cached pixmap using the emitted local transform.

## Parameters

| Component | Parameter |
| --- | --- |
| Target cadence | 30 FPS / 33 ms, one `PreciseTimer` |
| Breathing | 3.6 s; X 0.998–1.002, Y 0.996–1.008 around a 1.002 centre |
| Float | 4.8 s; ±1.5 logical pixels, inside the window only |
| Sway | 6.4 s; ±0.7 degrees |
| Drag tilt | opposite horizontal drag direction; configured and effective maximum ±4.0 degrees |
| Drag smoothing | time-normalized exponential smoothing, base factor 0.28 |
| Release | ease-out cubic over 220 ms; no bounce or widget inertia |

While dragging, breathing, float, and sway are paused and only the drag tilt remains. At release, the `QWidget` keeps the user-selected position; its local rotation returns to exactly neutral before idle motion resumes.

## Alpha pivot, render order, and clipping protection

The runtime image Alpha box is read at startup with Pillow, then projected to the 280 x 420 logical canvas. The current input calculates source bounds `(240, 42, 782, 1495)` and feet anchor `(139.7265625, 408.7890625)` in window coordinates. Those numbers are observations, not hard-coded runtime constants.

Every paint applies transforms in this order:

1. overall float translation;
2. translate to the feet-near Alpha-bound bottom-centre anchor;
3. rotate;
4. scale;
5. translate back;
6. draw the cached 280 x 420 pixmap.

At initialization, the window evaluates conservative sign combinations of maximum breathing, float, sway, and drag rotation against the actual Alpha bounds. If ±4 degrees would clip, it reduces only the effective drag limit; it does not enlarge the window or modify the image. The current asset accepts the full ±4.0-degree limit.

## Lifecycle and performance

In Stage 8, `showEvent` starts or resumes the controller, `hideEvent` pauses behavior time and stops its only timer, and `closeEvent` enters terminal `STOPPED`. The timer updates the separate timer-free behavior controller before calculating the final transform. Animation still never changes the window's desktop position, fixed size, or transparency. Per frame the work remains a few state/time checks, trigonometric calculations, and one cached-pixmap repaint; there is no disk polling, background worker, timer per effect, or frame logging.

## Diagnostics and automated tests

`scripts/render_animation_diagnostics.py` creates inspection-only files under `assets/analysis/animation/`:

- `idle_motion_contact_sheet.png`
- `drag_tilt_contact_sheet.png`
- `transform_bounds_overlay.png`
- `animation_parameter_summary.json`

The contact sheets are diagnostic visualizations, not character frame assets. `scripts/smoke_test_animation.py --offscreen` validates a four-second event-loop run, transform changes, unchanged desktop position during idle, drag tilt in both directions, release return, clipping safety, and asset hash. Unit and rendering tests cover bounds, ranges, controller lifecycle, drag smoothing, cached painting, alpha safety, and the protected PNG hash.

## Stage 9 extension and manual acceptance

Stage 9 retains the same timer and adds its click transform plus an identity fade before animation pause. The user still needs to inspect the real Windows desktop for natural breathing/click response, state distinction, drag feel, clipping, transparent edges, tray and topmost behavior, and idle CPU use. Alpha-aware interaction does not provide true lower-window pixel pass-through. Saved position, tray, and settings are documented in `interaction_tray_settings.md`; blinking/expressions, random travel, sound, dialogue, and packaging remain absent.

Stage 9 is implemented and awaiting real-desktop confirmation before Stage 10.

# Stage 8 behavior state machine

## Goal and boundaries

Stage 8 adds deterministic, testable orchestration above the Stage 7 paint-transform animation. It changes only animation parameters and state timing. It never moves the desktop window, loads or draws the character, reads global mouse position, writes settings, creates tray objects, or modifies the approved PNG.

## States and priority

Stage 9 extends this Stage 8 baseline with `CLICK_REACTION`; full interaction semantics are documented in `interaction_tray_settings.md`.

| State | Purpose |
| --- | --- |
| `STARTING` | 0.45-second identity-to-calm entrance after first show |
| `IDLE_CALM` | normal breathing, float, and subtle sway |
| `IDLE_QUIET` | normal breathing, 0.30 float, 0.15 sway |
| `IDLE_SWAY` | normal breathing, 0.80 float, 1.30 sway multiplier; final maximum 0.91 degrees |
| `RESTING` | 1.40 breathing period, 0.55 breathing amplitude, no float/sway, fixed 0.20-degree lean |
| `DRAGGING` | immediate user override; 0.30 breathing and drag-controlled rotation |
| `SETTLING` | Stage 7 220 ms cubic return; automatic switching suspended |
| `PAUSED` | hidden-window suspension with frozen state elapsed time |
| `STOPPED` | terminal close state with no timer or future transition |

Priority is now `STOPPED > PAUSED > DRAGGING > SETTLING > CLICK_REACTION > STARTING > automatic states`. The implementation uses `PetState`, not scattered integers or display strings.

## Transitions

Startup enters `IDLE_CALM`. Automatic states use the explicit transition table below and never self-loop:

- `IDLE_CALM` → `IDLE_QUIET`, `IDLE_SWAY`, or `RESTING`;
- `IDLE_QUIET` → `IDLE_CALM` or `IDLE_SWAY`;
- `IDLE_SWAY` → `IDLE_CALM` or `IDLE_QUIET`;
- `RESTING` → `IDLE_CALM` or `IDLE_QUIET`.

Any active automatic or starting state can be overridden by `DRAGGING`. Release enters `SETTLING`; completion restores the frozen pre-drag base state and its remaining duration. A re-drag during settling keeps that original recovery target. Hiding enters `PAUSED`; showing restores the saved base state. Closing enters `STOPPED`, which has no outgoing transitions.

`StateTransition` records fixed `TransitionReason` values, elapsed state time, and the next scheduled duration. Runtime history is bounded to the latest 100 transitions.

## Reproducible scheduling

`BehaviorScheduler` is pure Python. It owns one `random.Random` instance and never touches module-level random state or system time. With `behavior_seed=None`, one 64-bit seed is generated via `secrets.randbits(64)` at scheduler initialization and exposed as `actual_seed`. Tests and diagnostics use fixed seed `20260805`.

Production durations are:

- calm: 8–14 seconds;
- quiet: 4–8 seconds;
- sway: 5–9 seconds;
- resting: 8–16 seconds.

Transition weights are:

- calm: quiet 0.40, sway 0.35, resting 0.25;
- quiet: calm 0.65, sway 0.35;
- sway: calm 0.70, quiet 0.30;
- resting: calm 0.75, quiet 0.25.

Random values are consumed only when scheduling a next state or duration, never every animation frame. `RESTING` cannot repeat directly.

## Profiles and smooth blending

`BehaviorAnimationProfile` contains breathing-period and amplitude multipliers, float and sway multipliers, fixed rotation, and startup motion strength. It produces a new effective `IdleMotionProfile`; the immutable base `AnimationConfig` remains unchanged.

Automatic profile transitions use sine easing over 0.35 seconds. Stage 7 phase calculations continue from the same elapsed time, so transitions adjust amplitude without resetting animation cycles. Startup blends from identity into calm over 0.45 seconds. Fixed resting tilt is also interpolated. Drag begins as a high-priority override; settling and recovery reuse the existing drag easing and then blend back to the saved base profile.

## Single-timer integration and lifecycle

`BehaviorController` creates no timer and accepts injected elapsed monotonic seconds. The existing `AnimationController` remains the only 30 FPS `QTimer` owner. Each animation tick performs this order:

1. update behavior state from elapsed time;
2. obtain the current smoothly blended profile;
3. apply it to the immutable Stage 7 idle profile;
4. calculate the deterministic idle transform;
5. apply drag or settling rotation override when active;
6. emit one final `AnimationTransform`.

`PetWindow.showEvent` starts or resumes this timer. `hideEvent` freezes behavior time and stops it. `closeEvent` enters `STOPPED` and stops it permanently. No background thread, second high-frequency timer, per-frame disk read, per-frame hash, repeated pixmap scaling, Alpha scan, or frame log is used.

## Diagnostics and tests

`scripts/render_behavior_diagnostics.py` performs an offline 90-second simulation and creates only inspection files under `assets/analysis/behavior/`:

- `behavior_state_graph.png`;
- `behavior_timeline.png`;
- `behavior_profile_comparison.png`;
- `behavior_drag_override.png`;
- `behavior_diagnostic_summary.json`.

`scripts/smoke_test_behavior.py --offscreen` uses accelerated but logically equivalent durations to exercise startup, at least three automatic transitions, drag override, settling recovery, pause/resume, and terminal stop without `time.sleep()`. Automated tests cover enum and transition rules, deterministic scheduling, global-random isolation, profiles, blending, clipping, lifecycle, caching, transparency, and desktop-position stability.

## Manual acceptance and limits

Real Windows observation is still required for startup naturalness, state distinction, resting readability, transition feel, drag recovery, transparency, topmost behavior, and CPU/memory behavior over at least 90 seconds.

Stage 9 now supplies paint-only click feedback, system tray, settings, and saved position while retaining this behavior foundation. The project still has no blinking, expressions, automatic movement, walking, jumping, edge climbing, cursor following, dialogue, sound, transparent-pixel click-through, startup registration, or packaging.

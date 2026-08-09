# Stage 9 interaction, tray, settings, and persistence

## Scope and protected asset

Stage 9 adds daily-use interaction without changing the approved `1024 x 1536` RGBA master. Startup validation still requires SHA-256 `6FD2E4CA948E250926A22428AA633AF83F487971086ABA92B1017C3599747A64`. All runtime scaling and tray-icon work uses the one cached `QImage`/`QPixmap`; the source PNG is never edited or reread during a click, frame, or size change. `assets/animations/` remains `.gitkeep` only.

## Click versus drag

On a left press, `PetWindow` records global and local points, a `QElapsedTimer` timestamp, and the cached-image Alpha hit. Movement is accumulated as Euclidean distance. QWidget movement and `DRAGGING` begin only after the distance reaches `QApplication.startDragDistance()`.

A release becomes a click only when it is the left button, both endpoints hit visible pixels, movement stays below the system threshold, hold time is at most 500 ms, no context menu is open, and behavior is neither `PAUSED` nor `STOPPED`. Right-click, transparent margin, long press, and every drag are rejected. Right-click menus remain available over the full rectangular window.

## Alpha hit testing

`interaction/hit_test.py` maps window coordinates through a centered keep-aspect fit to the cached 1024 x 1536 source. All three approved 2:3 sizes map without crop or stretch. Points outside the window/image return false. Source Alpha >= 16 is interactive; lower Alpha is not. The code does not use `setMask()` and does not claim OS-level mouse pass-through: transparent window pixels still block underlying windows.

## CLICK_REACTION and curve

Priority is `STOPPED > PAUSED > DRAGGING > SETTLING > CLICK_REACTION > STARTING > automatic states`. `CLICK_REACTION` is user-triggered only and cannot self-loop or enter the scheduler.

The timer-free `InteractionController` freezes the prior automatic/starting state's elapsed and scheduled duration, emits `click_started`, and is updated by the sole animation tick. Drag immediately cancels the paint response and enters `DRAGGING`. At 260 ms it emits `click_finished` and restores the original state with its remaining time unchanged.

The deterministic feet-anchored curve is:

- 0–90 ms: X scale 1.000 to 1.010, Y scale 1.000 to 0.992, Y offset 0 to +1.0;
- 90–180 ms: X 1.010 to 0.997, Y 0.992 to 1.003, offset +1.0 to -0.5;
- 180–260 ms: smooth return to exact identity.

It adds no opacity or rotation, never moves the QWidget, uses no random value, and passes all three clipping checks.

## Settings schema and storage

`UserSettings` is a frozen, slotted schema-version-1 dataclass. It stores only size, topmost, animation, automatic behavior, click feedback, remember-position, optional paired X/Y, and optional screen name. Approved `PetSize` values are 240 x 360, 280 x 420, and 320 x 480; 280 x 420 is default.

`SettingsRepository` uses an explicit `QSettings(..., IniFormat)` file named `settings.ini` below `QStandardPaths.AppConfigLocation` in `DesktopPet`. It calls `sync()` and checks status. Tests inject a temporary directory. Invalid values recover independently to safe defaults, unknown keys are ignored, incomplete coordinates are cleared, and no asset path, credential, username, registry value, or project file is stored.

`SettingsService` owns the current immutable value, saves only on explicit operations, and emits `settings_changed`. The repository never imports or manipulates a QWidget.

## Position save and recovery

When enabled, position persistence records top-left X/Y, screen name, and size on drag release, size change, reset, and normal exit—not during mouse move or animation frames. Startup accepts a saved rectangle only if at least 40 x 40 logical pixels intersect an available screen. Negative-coordinate displays are supported.

If a named display was removed or coordinates no longer meet the visibility rule after resolution, DPI, or taskbar changes, the window falls back to the current-pointer screen's usable bottom-right corner and saves the corrected position. With remember-position disabled, saved coordinates are cleared/ignored and the same Stage 6 default is used.

## Runtime size and topmost changes

Size changes rebuild only the smooth scaled pixmap and projected Alpha bounds from cached memory. They recalculate the feet pivot and clipping result, preserve state and animation phase, keep 2:3 geometry, and attempt to hold the global feet centre stable before screen-visibility correction.

Topmost switching retains `FramelessWindowHint` and `Tool`. Because Qt can hide a window while changing flags, `PetWindow` suppresses lifecycle pause/restart for that internal hide/show, restores the old position and visibility, and never recreates the QApplication, window, or controllers.

## Animation versus automatic behavior

Disabling animation uses the existing timer for a 260 ms identity fade, then stops that timer. The static pet remains draggable and menus remain available. Re-enabling resumes through the existing paused-state profile blend rather than jumping to an old transform.

Disabling automatic behavior is different: the timer and calm breathing/float/sway remain active, while scheduling is suspended on `IDLE_CALM`. Drag and click overrides still work. Disabling click feedback rejects clicks without changing drag or cached Alpha testing.

## ActionRegistry, tray, and window menu

One `ActionRegistry` owns all nine persistent actions: show/hide, pause/resume, three exclusive sizes, always-on-top, settings, reset position, and quit. Window and tray menus build separate menu shells around those same `QAction` objects; signal connections and business callbacks are not duplicated. Text, checks, and hide availability synchronize from current settings and visibility.

`TrayController` first calls `QSystemTrayIcon.isSystemTrayAvailable()`. When available, it crops the cached source Alpha bounds into an in-memory square transparent `QIcon`, creates one tray icon, and restores/raises the existing pet on double-click. When unavailable it warns once, creates no tray object, keeps the pet working, and disables hiding so the application cannot become unreachable.

## Settings dialog and lifecycle

The ordinary non-topmost `SettingsDialog` offers the three sizes and five booleans. Apply persists immediately without closing; OK applies and closes; Cancel discards pending controls; Restore Defaults changes controls only until Apply/OK. `DesktopPetApplicationController` lazily owns at most one dialog.

The application controller also owns exactly one pet window, animation controller, behavior controller, interaction controller, repository, service, action registry, and tray controller. Hiding pauses the timer but is not exit. Normal exit saves settings/position, enters terminal `STOPPED`, stops the sole timer, hides the tray icon, and closes the settings dialog. No background thread exists.

## Diagnostics and automated verification

`render_interaction_diagnostics.py` generates under `assets/analysis/interaction/`:

- `alpha_hit_test_map.png`;
- `click_reaction_contact_sheet.png`;
- `size_comparison.png`;
- `settings_schema.json`;
- `interaction_diagnostic_summary.json`.

These are inspection artifacts, not runtime animation frames. Dedicated interaction, settings, and tray smoke scripts run offscreen. Unit/integration tests cover Alpha mapping, threshold edges, curve keyframes, state recovery/override, settings corruption, dialog semantics, negative/removed displays, feet-anchored sizes, shared actions, tray fallback, single-controller ownership, one high-frequency timer, no per-frame writes, protected hash, and unchanged animations directory.

## Manual acceptance and known limits

Automatic checks cannot confirm real Windows tray rendering, natural click feel, taskbar integration, topmost changes against other applications, DPI/multi-monitor transitions, long-run CPU/memory, or absence of a residual process after interactive exit. The user must run `run.ps1` and confirm these.

Transparent pixels still block lower-window mouse input. Stage 9 has no true pixel pass-through, automatic movement, walking/running/jumping, blinking/expression frames, dialogue, sound, startup registration, network/update function, or packaged executable.

Stage 10 remains unstarted. It may begin only after user approval and is limited to final testing, optimization, and PyInstaller packaging.

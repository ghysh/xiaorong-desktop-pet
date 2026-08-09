# Transparent window prototype (Stage 6 baseline, extended in Stage 9)

Stage 6 established the fixed 280 x 420 transparent, frameless, always-on-top `Tool` window using the approved Plan B full-body runtime master. It uses the pointer screen's usable bottom-right area at startup, supports negative-coordinate displays, keeps a 40 x 40 visible portion after a left drag, and keeps an exit-only right-click menu.

Stages 7 and 8 preserve that baseline while adding paint transforms and state orchestration. Stage 9 adds three user-selected fixed sizes, Alpha-aware clicks, shared menus/tray, and saved position; it still never moves the `QWidget` automatically or edits the asset. See [the animation system](animation_system.md), [the behavior state machine](behavior_state_machine.md), and [Stage 9 interaction and settings](interaction_tray_settings.md).

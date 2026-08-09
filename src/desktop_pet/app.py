"""Release-ready application lifecycle, diagnostics, and explicit smoke-test mode."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QIcon, QScreen
from PySide6.QtWidgets import QApplication

from desktop_pet.config import WINDOW_TITLE, DialogueBubbleConfig, PetWindowConfig
from desktop_pet.dialogue.controller import DialogueController
from desktop_pet.dialogue.repository import DialogueFileError, DialogueRepository
from desktop_pet.dialogue.selector import DialogueSelector
from desktop_pet.error_reporting import install_exception_hook, report_startup_failure
from desktop_pet.paths import APPLICATION_ICON, CLICK_DIALOGUE_FILE, FULLBODY_RUNTIME_MASTER, is_frozen
from desktop_pet.settings.model import PetSize, UserSettings
from desktop_pet.settings.repository import SettingsRepository
from desktop_pet.settings.service import SettingsService, resolve_window_position
from desktop_pet.ui.action_registry import ActionRegistry
from desktop_pet.ui.dialogue_bubble import DialogueBubble
from desktop_pet.ui.geometry import calculate_bottom_right_position
from desktop_pet.ui.pet_window import (
    EXPECTED_RUNTIME_ASSET_SHA256,
    PetAssetError,
    PetWindow,
    runtime_asset_sha256,
)
from desktop_pet.ui.settings_dialog import SettingsDialog
from desktop_pet.ui.tray_controller import TrayController
from desktop_pet.version import __version__

ORGANIZATION_NAME = "DesktopPetProject"
APPLICATION_NAME = "小融"


@dataclass(frozen=True, slots=True)
class RuntimeOptions:
    release_smoke_test: bool = False
    quit_after_ms: int | None = None
    config_dir: Path | None = None
    no_tray: bool = False
    smoke_result: Path | None = None


def parse_runtime_options(argv: list[str]) -> RuntimeOptions:
    """Parse explicit developer smoke switches; ordinary launch remains unchanged."""
    parser = argparse.ArgumentParser(prog="小融")
    parser.add_argument("--release-smoke-test", action="store_true")
    parser.add_argument("--quit-after-ms", type=int)
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--no-tray", action="store_true")
    parser.add_argument("--smoke-result", type=Path)
    namespace = parser.parse_args(argv)
    if namespace.quit_after_ms is not None and not namespace.release_smoke_test:
        parser.error("--quit-after-ms is only valid with --release-smoke-test")
    if namespace.smoke_result is not None and not namespace.release_smoke_test:
        parser.error("--smoke-result is only valid with --release-smoke-test")
    if namespace.release_smoke_test:
        if namespace.smoke_result is None:
            parser.error("--release-smoke-test requires --smoke-result")
        duration = 1500 if namespace.quit_after_ms is None else namespace.quit_after_ms
        if not 100 <= duration <= 60_000:
            parser.error("--quit-after-ms must be between 100 and 60000")
    else:
        duration = None
    return RuntimeOptions(
        release_smoke_test=namespace.release_smoke_test,
        quit_after_ms=duration,
        config_dir=namespace.config_dir.resolve() if namespace.config_dir is not None else None,
        no_tray=namespace.no_tray,
        smoke_result=namespace.smoke_result.resolve() if namespace.smoke_result is not None else None,
    )


def create_application(argv: list[str] | None = None) -> QApplication:
    """Create or reuse QApplication with stable release metadata."""
    application = QApplication.instance()
    if application is None:
        application = QApplication(sys.argv if argv is None else argv)
    if not isinstance(application, QApplication):
        raise RuntimeError("The existing Qt application is not a QApplication instance.")
    application.setOrganizationName(ORGANIZATION_NAME)
    application.setOrganizationDomain("")
    application.setApplicationName(APPLICATION_NAME)
    application.setApplicationDisplayName(WINDOW_TITLE)
    application.setApplicationVersion(__version__)
    icon = QIcon(str(APPLICATION_ICON))
    if icon.isNull():
        raise RuntimeError(f"Application icon could not be loaded: {APPLICATION_ICON}")
    application.setWindowIcon(icon)
    return application


def create_pet_window(config: PetWindowConfig | None = None) -> PetWindow:
    return PetWindow(config)


def pointer_screen() -> QScreen:
    screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
    if screen is None:
        raise RuntimeError("No display screen is available for the desktop-pet startup position.")
    return screen


def default_pet_position(window: PetWindow) -> QPoint:
    screen = pointer_screen()
    return calculate_bottom_right_position(screen.availableGeometry(), window.size(), window.config.startup_margin)


def position_pet_window(window: PetWindow) -> None:
    window.move(default_pet_position(window))


class DesktopPetApplicationController(QObject):
    """Own every application object and coordinate bounded persistence and shutdown."""

    def __init__(
        self,
        application: QApplication,
        *,
        config_directory: Path | str | None = None,
        enable_tray: bool = True,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent or application)
        self.application = application
        self.settings_repository = SettingsRepository(config_directory)
        self.settings_service = SettingsService(self.settings_repository, parent=self)
        initial = self.settings_service.current
        self.pet_window = create_pet_window(
            PetWindowConfig(width=initial.size.width, height=initial.size.height, always_on_top=initial.always_on_top)
        )
        self.animation_controller = self.pet_window.animation_controller
        self.behavior_controller = self.pet_window.behavior_controller
        self.interaction_controller = self.pet_window.interaction_controller
        self.action_player = self.animation_controller.action_player
        self.blink_controller = self.animation_controller.blink_controller
        self.dialogue_repository = DialogueRepository(CLICK_DIALOGUE_FILE)
        try:
            dialogues = self.dialogue_repository.load()
        except DialogueFileError as error:
            print(f"小融警告：单击对白已禁用；{error}", file=sys.stderr)
            self.dialogue_selector: DialogueSelector | None = None
        else:
            self.dialogue_selector = DialogueSelector(dialogues)
        self.dialogue_bubble = DialogueBubble(
            DialogueBubbleConfig(),
            always_on_top=initial.always_on_top,
        )
        self.dialogue_controller = DialogueController(
            self.dialogue_repository,
            self.dialogue_selector,
            self.dialogue_bubble,
            self.pet_window,
            lambda: self.settings_service.current.click_reaction_enabled,
            parent=self,
        )
        self._settings_dialog: SettingsDialog | None = None
        self._applied_settings = initial
        self._applying_settings = False
        self._stopping = False

        self.action_registry = ActionRegistry(
            self.settings_service,
            show_hide_callback=self.toggle_window_visibility,
            show_settings_callback=self.show_settings,
            reset_position_callback=self.reset_position,
            quit_callback=self.request_quit,
            parent=self,
        )
        self.pet_window.set_action_registry(self.action_registry)
        self.tray_controller = TrayController(
            self.pet_window,
            self.action_registry,
            restore_callback=self.show_pet_window,
            enabled=enable_tray,
            parent=self,
        )
        self.application.setQuitOnLastWindowClosed(not self.tray_controller.available)

        self.settings_service.settings_changed.connect(self._apply_settings)
        self.interaction_controller.character_clicked.connect(self.dialogue_controller.show_random_dialogue)
        self.pet_window.position_commit_requested.connect(self._save_position)
        self.pet_window.close_requested.connect(self.request_quit)
        self.application.aboutToQuit.connect(self.shutdown)

        self.pet_window.set_behavior_enabled(initial.behavior_enabled)
        self.pet_window.set_click_reaction_enabled(initial.click_reaction_enabled)
        self.pet_window.set_animation_enabled(initial.animation_enabled)
        self._restore_startup_position(initial)
        self._sync_actions()

    @property
    def settings_dialog(self) -> SettingsDialog | None:
        return self._settings_dialog

    def start(self) -> None:
        self.pet_window.show()
        self.tray_controller.show()
        self._sync_actions()

    def toggle_window_visibility(self) -> None:
        if self.pet_window.isVisible():
            if not self.tray_controller.available:
                print("小融警告：系统托盘不可用，无法隐藏桌宠。", file=sys.stderr)
                self._sync_actions()
                return
            self.pet_window.hide()
        else:
            self.show_pet_window()
        self._sync_actions()

    def show_pet_window(self) -> None:
        self.pet_window.show()
        self.pet_window.raise_()
        self._sync_actions()

    def show_settings(self) -> None:
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self.settings_service, self.pet_window)
        self._settings_dialog.refresh_from_current()
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def reset_position(self) -> None:
        self.settings_service.reset_position()
        self.pet_window.move(default_pet_position(self.pet_window))
        self._save_position(self.pet_window.pos())

    def request_quit(self) -> None:
        self.shutdown()
        self.application.quit()

    def shutdown(self) -> None:
        if self._stopping:
            return
        self._stopping = True
        if self.settings_service.current.remember_position:
            self._save_position(self.pet_window.pos())
        else:
            self.settings_service.save_current()
        self.animation_controller.shutdown()
        self.dialogue_controller.shutdown()
        self.tray_controller.shutdown()
        if self._settings_dialog is not None:
            self._settings_dialog.close()

    def smoke_snapshot(self) -> dict[str, object]:
        """Return bounded, non-sensitive release data before terminal shutdown."""
        return {
            "status": "passed",
            "version": __version__,
            "application_name": self.application.applicationName(),
            "application_display_name": self.application.applicationDisplayName(),
            "application_version": self.application.applicationVersion(),
            "application_icon_available": not self.application.windowIcon().isNull(),
            "frozen": is_frozen(),
            "process_id": os.getpid(),
            "runtime_asset_path": str(FULLBODY_RUNTIME_MASTER.resolve()),
            "runtime_asset_sha256": runtime_asset_sha256(FULLBODY_RUNTIME_MASTER),
            "window_size": list(self.pet_window.size().toTuple()),
            "translucent_background": self.pet_window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground),
            "window_count": sum(isinstance(widget, PetWindow) for widget in QApplication.topLevelWidgets()),
            "high_frequency_timer_count": len(self.pet_window.findChildren(QTimer)),
            "dialogue_single_shot_timer_count": len(self.dialogue_bubble.findChildren(QTimer)),
            "dialogue_available": self.dialogue_controller.available,
            "dialogue_file_encoding": self.dialogue_repository.encoding,
            "animation_controller": self.animation_controller is not None,
            "runtime_action_ids": list(self.pet_window.runtime_action_registry.action_ids),
            "action_source_load_count": self.pet_window.action_asset_cache.source_load_count,
            "action_scale_count": self.pet_window.action_asset_cache.scale_count,
            "behavior_state": self.behavior_controller.current_state.name,
            "settings_path": str(self.settings_repository.file_path),
            "tray_available": self.tray_controller.available,
            "asset_load_count": self.pet_window.runtime_asset_load_count,
            "tray_icon_creation_count": self.tray_controller.icon_creation_count,
            "position": [self.pet_window.x(), self.pet_window.y()],
        }

    def _restore_startup_position(self, settings: UserSettings) -> None:
        restored, corrected = resolve_window_position(
            settings,
            self.pet_window.size(),
            self._screen_geometries(),
            default_pet_position(self.pet_window),
        )
        self.pet_window.move(restored)
        if corrected and settings.remember_position:
            self._save_position(restored)

    def _apply_settings(self, settings: UserSettings) -> None:
        if self._applying_settings:
            return
        self._applying_settings = True
        previous = self._applied_settings
        try:
            if settings.size is not previous.size:
                self.pet_window.set_pet_size(settings.size)
            if settings.always_on_top is not previous.always_on_top:
                self.pet_window.set_always_on_top(settings.always_on_top)
                self.dialogue_controller.set_always_on_top(settings.always_on_top)
            if settings.behavior_enabled is not previous.behavior_enabled:
                self.pet_window.set_behavior_enabled(settings.behavior_enabled)
            if settings.click_reaction_enabled is not previous.click_reaction_enabled:
                self.pet_window.set_click_reaction_enabled(settings.click_reaction_enabled)
                self.dialogue_controller.set_enabled(settings.click_reaction_enabled)
            if settings.animation_enabled is not previous.animation_enabled:
                self.pet_window.set_animation_enabled(settings.animation_enabled)
            self._applied_settings = settings
        finally:
            self._applying_settings = False
        if settings.size is not previous.size and settings.remember_position:
            self._save_position(self.pet_window.pos())
        self._sync_actions()

    def _save_position(self, position: QPoint) -> None:
        if not self.settings_service.current.remember_position:
            return
        screen = QGuiApplication.screenAt(self.pet_window.frameGeometry().center()) or pointer_screen()
        self.settings_service.save_position(QPoint(position), screen.name().strip() or None)

    def _sync_actions(self) -> None:
        self.action_registry.sync(
            self.settings_service.current,
            window_visible=self.pet_window.isVisible(),
            tray_available=self.tray_controller.available,
        )

    @staticmethod
    def _screen_geometries() -> dict[str, QRect]:
        geometries: dict[str, QRect] = {}
        for index, screen in enumerate(QGuiApplication.screens()):
            geometries[screen.name().strip() or f"screen-{index}"] = screen.availableGeometry()
        if not geometries:
            raise RuntimeError("No display screen is available for position restoration.")
        return geometries


def runtime_resource_status() -> str:
    if not FULLBODY_RUNTIME_MASTER.is_file():
        return f"missing: {FULLBODY_RUNTIME_MASTER}"
    try:
        digest = runtime_asset_sha256(FULLBODY_RUNTIME_MASTER)
    except OSError as error:
        return f"unreadable: {error}"
    if digest != EXPECTED_RUNTIME_ASSET_SHA256:
        return f"hash mismatch: {digest}"
    return "approved runtime asset verified"


def _write_smoke_result(path: Path, snapshot: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(argv: list[str] | None = None) -> int:
    """Run normally or execute the explicit frozen-release smoke mode."""
    options = parse_runtime_options([] if argv is None else argv)
    try:
        application = create_application(["小融"])
        install_exception_hook(resource_status_provider=runtime_resource_status)
        controller = DesktopPetApplicationController(
            application,
            config_directory=options.config_dir,
            enable_tray=not options.no_tray,
        )
        controller.start()
        if options.release_smoke_test:
            def finish_smoke_test() -> None:
                assert options.smoke_result is not None
                size_switch_results: list[list[int]] = []
                for size in PetSize:
                    controller.settings_service.set_size(size)
                    application.processEvents()
                    size_switch_results.append(list(controller.pet_window.size().toTuple()))
                controller.settings_service.set_size(PetSize.DEFAULT)
                application.processEvents()
                saved_position = controller.pet_window.pos() + QPoint(3, 4)
                controller.pet_window.move(saved_position)
                controller._save_position(saved_position)
                snapshot = controller.smoke_snapshot()
                snapshot["size_switch_results"] = size_switch_results
                snapshot["position_saved"] = (
                    controller.settings_service.current.window_x == saved_position.x()
                    and controller.settings_service.current.window_y == saved_position.y()
                )
                controller.shutdown()
                snapshot["settings_file_created"] = controller.settings_repository.file_path.is_file()
                snapshot["terminal_state"] = controller.behavior_controller.current_state.name
                _write_smoke_result(options.smoke_result, snapshot)
                application.quit()

            QTimer.singleShot(options.quit_after_ms or 1500, finish_smoke_test)
        return application.exec()
    except (OSError, PetAssetError, RuntimeError, ValueError) as error:
        report_startup_failure(error, resource_status=runtime_resource_status())
        print(f"小融启动失败（{type(error).__name__}）：{error}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    return run(sys.argv[1:] if argv is None else argv)

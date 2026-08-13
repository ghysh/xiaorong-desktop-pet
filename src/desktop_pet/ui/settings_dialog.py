"""Non-topmost settings dialog for the Stage 9 user preferences."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
)

from desktop_pet.settings.model import PetSize, UserSettings
from desktop_pet.settings.service import SettingsService


class SettingsDialog(QDialog):
    """Edit a copy of settings; only Apply or OK persists it through the service."""

    def __init__(self, settings_service: SettingsService, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self._settings_service = settings_service
        self._restore_defaults_requested = False
        self.setWindowTitle("小融设置")
        self.setModal(False)

        self.size_combo = QComboBox(self)
        for size, label in (
            (PetSize.SMALL, "240 × 360"),
            (PetSize.DEFAULT, "280 × 420"),
            (PetSize.LARGE, "320 × 480"),
        ):
            self.size_combo.addItem(label, size.name)
        self.always_on_top_checkbox = QCheckBox("始终置顶", self)
        self.animation_enabled_checkbox = QCheckBox("启用动画", self)
        self.behavior_enabled_checkbox = QCheckBox("启用自动待机状态", self)
        self.click_reaction_enabled_checkbox = QCheckBox("启用单击反馈", self)
        self.remember_position_checkbox = QCheckBox("记住窗口位置", self)

        form = QFormLayout()
        form.addRow("显示尺寸：", self.size_combo)
        form.addRow(self.always_on_top_checkbox)
        form.addRow(self.animation_enabled_checkbox)
        form.addRow(self.behavior_enabled_checkbox)
        form.addRow(self.click_reaction_enabled_checkbox)
        form.addRow(self.remember_position_checkbox)

        self.restore_defaults_button = QPushButton("恢复默认设置", self)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        button_row = QHBoxLayout()
        button_row.addWidget(self.restore_defaults_button)
        button_row.addStretch(1)
        button_row.addWidget(self.button_box)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(button_row)

        self.restore_defaults_button.clicked.connect(self._show_defaults)
        self.button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_changes)
        self.button_box.accepted.connect(self._accept_changes)
        self.button_box.rejected.connect(self.reject)
        self.refresh_from_current()

    def showEvent(self, event: QShowEvent) -> None:
        self.refresh_from_current()
        super().showEvent(event)

    def refresh_from_current(self) -> None:
        self._load_controls(self._settings_service.current)
        self._restore_defaults_requested = False

    def apply_changes(self) -> UserSettings:
        settings = self._settings_from_controls()
        self._settings_service.apply(settings)
        self._restore_defaults_requested = False
        return settings

    def _accept_changes(self) -> None:
        self.apply_changes()
        self.accept()

    def _show_defaults(self) -> None:
        self._load_controls(UserSettings())
        self._restore_defaults_requested = True

    def _load_controls(self, settings: UserSettings) -> None:
        index = self.size_combo.findData(settings.size.name)
        self.size_combo.setCurrentIndex(index)
        self.always_on_top_checkbox.setChecked(settings.always_on_top)
        self.animation_enabled_checkbox.setChecked(settings.animation_enabled)
        self.behavior_enabled_checkbox.setChecked(settings.behavior_enabled)
        self.click_reaction_enabled_checkbox.setChecked(settings.click_reaction_enabled)
        self.remember_position_checkbox.setChecked(settings.remember_position)

    def _settings_from_controls(self) -> UserSettings:
        current = self._settings_service.current
        keep_position = self.remember_position_checkbox.isChecked() and not self._restore_defaults_requested
        defaults = UserSettings()
        return UserSettings(
            size=PetSize[self.size_combo.currentData()],
            always_on_top=self.always_on_top_checkbox.isChecked(),
            animation_enabled=self.animation_enabled_checkbox.isChecked(),
            behavior_enabled=self.behavior_enabled_checkbox.isChecked(),
            drowsy_sleep_enabled=(
                defaults.drowsy_sleep_enabled
                if self._restore_defaults_requested
                else current.drowsy_sleep_enabled
            ),
            click_reaction_enabled=self.click_reaction_enabled_checkbox.isChecked(),
            remember_position=self.remember_position_checkbox.isChecked(),
            window_x=current.window_x if keep_position else None,
            window_y=current.window_y if keep_position else None,
            screen_name=current.screen_name if keep_position else None,
        )

"""Render non-runtime dialogue bubble samples for visual inspection."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

from desktop_pet.app import create_application
from desktop_pet.paths import DIALOGUE_ANALYSIS_DIR
from desktop_pet.settings.model import PetSize
from desktop_pet.ui.dialogue_bubble import DialogueBubble, calculate_bubble_placement

SAMPLES = {
    "short": "今天也要开心呀。",
    "medium": "刚才是在叫我吗？我一直都在这里陪着你。 Desktop Pet is ready!",
    "long": (
        "这是一段用于检查长中文对白自动换行、标点显示和阅读节奏的诊断文字。"
        "即使中文之间没有空格，气泡也应保持清晰，并且不能越过屏幕边缘。"
    ),
}


def _capture(bubble: DialogueBubble, text: str, pet: QRect, screen: QRect) -> QImage:
    bubble.show_dialogue(text, pet, screen)
    application = create_application(["dialogue-diagnostics"])
    application.processEvents()
    return bubble.grab().toImage()


def _save_composite(path: Path, bubble_image: QImage, background: QColor, label: str) -> None:
    canvas = QImage(QSize(720, 420), QImage.Format.Format_ARGB32_Premultiplied)
    canvas.fill(background)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QColor(78, 73, 88) if background.lightness() > 128 else QColor(232, 227, 240))
    painter.setFont(QFont("Microsoft YaHei UI", 12))
    painter.drawText(QRect(24, 18, 672, 34), Qt.AlignmentFlag.AlignLeft, label)
    painter.drawImage(QPoint((canvas.width() - bubble_image.width()) // 2, 90), bubble_image)
    painter.end()
    if not canvas.save(str(path)):
        raise RuntimeError(f"Could not save dialogue diagnostic: {path}")


def _positions_diagnostic(path: Path) -> list[dict[str, object]]:
    canvas = QImage(QSize(1200, 760), QImage.Format.Format_ARGB32_Premultiplied)
    canvas.fill(QColor(236, 233, 242))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setFont(QFont("Microsoft YaHei UI", 9))
    scenarios = (
        ("左上", QRect(0, 0, 800, 500), QRect(4, 4, 180, 360)),
        ("右上", QRect(0, 0, 800, 500), QRect(620, 4, 180, 360)),
        ("右下/任务栏", QRect(0, 0, 800, 460), QRect(620, 260, 180, 360)),
        ("负坐标副屏", QRect(-800, -120, 800, 500), QRect(-230, 100, 180, 360)),
    )
    results: list[dict[str, object]] = []
    panel_origins = (QPoint(20, 42), QPoint(610, 42), QPoint(20, 400), QPoint(610, 400))
    scale = 0.65
    for (name, screen, pet), panel in zip(scenarios, panel_origins, strict=True):
        placement = calculate_bubble_placement(
            QSize(260, 120), pet, screen, screen_margin=12, pet_gap=8
        )
        local_pet = QRect(
            panel.x() + round((pet.x() - screen.x()) * scale),
            panel.y() + round((pet.y() - screen.y()) * scale),
            round(pet.width() * scale),
            round(pet.height() * scale),
        )
        local_bubble = QRect(
            panel.x() + round((placement.position.x() - screen.x()) * scale),
            panel.y() + round((placement.position.y() - screen.y()) * scale),
            round(260 * scale),
            round(120 * scale),
        )
        local_screen = QRect(panel, QSize(round(screen.width() * scale), round(screen.height() * scale)))
        painter.setPen(QPen(QColor(130, 124, 145), 1))
        painter.setBrush(QColor(250, 249, 252))
        painter.drawRect(local_screen)
        painter.setBrush(QColor(88, 82, 98, 190))
        painter.drawRoundedRect(local_pet, 16, 16)
        painter.setBrush(QColor(248, 246, 251))
        painter.drawRoundedRect(local_bubble, 10, 10)
        painter.setPen(QColor(55, 52, 62))
        painter.drawText(local_screen.adjusted(8, 5, -8, -5), Qt.AlignmentFlag.AlignTop, name)
        results.append(
            {
                "name": name,
                "screen": list(screen.getRect()),
                "pet": list(pet.getRect()),
                "bubble": [placement.position.x(), placement.position.y(), 260, 120],
                "tail": placement.tail_direction.value,
            }
        )
    painter.end()
    if not canvas.save(str(path)):
        raise RuntimeError(f"Could not save dialogue positioning diagnostic: {path}")
    return results


def _three_sizes_diagnostic(path: Path, bubble_image: QImage) -> None:
    canvas = QImage(QSize(1000, 620), QImage.Format.Format_ARGB32_Premultiplied)
    canvas.fill(QColor(242, 239, 246))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setFont(QFont("Microsoft YaHei UI", 10))
    x = 40
    for size in PetSize:
        scale = 0.62
        width = round(size.width * scale)
        height = round(size.height * scale)
        bottom = 570
        pet_rect = QRect(x + 35, bottom - height, width, height)
        image = bubble_image.scaledToWidth(min(220, bubble_image.width()), Qt.TransformationMode.SmoothTransformation)
        painter.drawImage(QPoint(x, pet_rect.top() - image.height() - 8), image)
        painter.setPen(QPen(QColor(125, 117, 140), 1))
        painter.setBrush(QColor(83, 77, 94, 190))
        painter.drawRoundedRect(pet_rect, 18, 18)
        painter.setPen(QColor(55, 52, 62))
        painter.drawText(QRect(x, 580, 260, 24), Qt.AlignmentFlag.AlignHCenter, f"{size.width} × {size.height}")
        x += 315
    painter.end()
    if not canvas.save(str(path)):
        raise RuntimeError(f"Could not save three-size diagnostic: {path}")


def main() -> int:
    application = create_application(["dialogue-diagnostics"])
    output = DIALOGUE_ANALYSIS_DIR
    output.mkdir(parents=True, exist_ok=True)
    bubble = DialogueBubble()
    bubble.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    pet = QRect(440, 420, 180, 380)
    screen = QRect(0, 0, 1200, 900)
    images: dict[str, QImage] = {}
    for name, text in SAMPLES.items():
        image = _capture(bubble, text, pet, screen)
        images[name] = image
        destination = output / f"dialogue_bubble_{name}.png"
        if not image.save(str(destination)):
            raise RuntimeError(f"Could not save dialogue diagnostic: {destination}")

    _save_composite(
        output / "dialogue_bubble_on_light.png",
        images["medium"],
        QColor(245, 242, 237),
        "浅色桌面可读性",
    )
    _save_composite(
        output / "dialogue_bubble_on_dark.png",
        images["medium"],
        QColor(31, 30, 38),
        "深色桌面可读性",
    )
    positions = _positions_diagnostic(output / "dialogue_bubble_positions.png")
    _three_sizes_diagnostic(output / "dialogue_bubble_three_sizes.png", images["short"])
    summary = {
        "status": "passed",
        "samples": {
            name: {"characters": len(text), "size": list(images[name].size().toTuple())}
            for name, text in SAMPLES.items()
        },
        "positions": positions,
        "pet_sizes": [list(size.value) for size in PetSize],
        "backgrounds": ["light", "dark"],
        "high_dpi_units": "Qt logical pixels",
        "runtime_resource": False,
    }
    (output / "dialogue_diagnostic_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    bubble.shutdown()
    application.processEvents()
    print(json.dumps({"status": "passed", "output": str(output), "files": 8}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

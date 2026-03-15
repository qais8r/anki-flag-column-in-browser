from __future__ import annotations

import aqt
from aqt.qt import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFont,
    QFontMetrics,
    QHBoxLayout,
    QLabel,
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QRadioButton,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
)
from .addon_config import (
    AddonSettings,
    OUTLINE_MODE_AUTO,
    OUTLINE_MODE_BLACK,
    OUTLINE_MODE_FLAG,
    OUTLINE_MODES,
    OUTLINE_MODE_WHITE,
    get_settings,
    save_settings,
)
from .browser_features import (
    FLAG_GLYPH,
    FLAG_PREVIEW_COLORS,
    flag_theme_qcolor,
    outline_color_for_mode,
    refresh_browser_view,
)


class FlagColumnSettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Flag Column Settings")

        layout = QVBoxLayout(self)
        content = QHBoxLayout()
        options = QVBoxLayout()
        options.addWidget(QLabel("Flag outline color"))

        self._buttons: dict[str, QRadioButton] = {}
        self._group = QButtonGroup(self)
        for label, mode in (
            ("Auto (match theme)", OUTLINE_MODE_AUTO),
            ("Always black", OUTLINE_MODE_BLACK),
            ("Always white", OUTLINE_MODE_WHITE),
            ("Match flag color", OUTLINE_MODE_FLAG),
        ):
            button = QRadioButton(label)
            self._group.addButton(button)
            self._buttons[mode] = button
            options.addWidget(button)

        options.addSpacing(12)
        self._state_prefix_checkbox = QCheckBox(
            "Show compact state badges in Sort Field", self
        )
        options.addWidget(self._state_prefix_checkbox)
        options.addStretch(1)
        content.addLayout(options, 1)

        previews = QHBoxLayout()
        previews.setSpacing(12)
        self._light_preview = _AnimatedFlagPreview(night_mode=False, parent=self)
        self._dark_preview = _AnimatedFlagPreview(night_mode=True, parent=self)

        for label, preview in (("Light", self._light_preview), ("Dark", self._dark_preview)):
            preview_column = QVBoxLayout()
            title = QLabel(label)
            title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            preview_column.addWidget(title)
            preview_column.addWidget(preview)
            previews.addLayout(preview_column)

        preview_panel = QVBoxLayout()
        preview_panel.addLayout(previews)
        preview_panel.addStretch(1)
        content.addLayout(preview_panel)
        content.setAlignment(preview_panel, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(content)

        self._apply_settings(get_settings())
        self._sync_preview_mode()
        for button in self._buttons.values():
            button.toggled.connect(self._on_mode_toggled)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_settings(self, settings: AddonSettings) -> None:
        current_mode = (
            settings.outline_mode
            if settings.outline_mode in OUTLINE_MODES
            else OUTLINE_MODE_AUTO
        )
        self._buttons[current_mode].setChecked(True)
        self._state_prefix_checkbox.setChecked(
            settings.show_state_prefixes_in_sort_field
        )

    def _sync_preview_mode(self) -> None:
        mode = self._selected_outline_mode()
        self._light_preview.set_outline_mode(mode)
        self._dark_preview.set_outline_mode(mode)

    def _on_mode_toggled(self, checked: bool) -> None:
        if checked:
            self._sync_preview_mode()

    def _selected_outline_mode(self) -> str:
        for mode, button in self._buttons.items():
            if button.isChecked():
                return mode
        return OUTLINE_MODE_AUTO

    def _selected_settings(self) -> AddonSettings:
        return AddonSettings(
            outline_mode=self._selected_outline_mode(),
            show_state_prefixes_in_sort_field=self._state_prefix_checkbox.isChecked(),
        )

    def accept(self) -> None:
        save_settings(self._selected_settings())
        refresh_browser_view(force_refetch=True)
        super().accept()


class _AnimatedFlagPreview(QWidget):
    _TICK_MS = 33
    _HOLD_MS = 450
    _FADE_MS = 650

    def __init__(self, night_mode: bool, parent=None) -> None:
        super().__init__(parent)
        self._night_mode = night_mode
        self._outline_mode = OUTLINE_MODE_AUTO
        self._phase_ms = 0
        self._current_index = 0
        self._next_index = 1 if len(FLAG_PREVIEW_COLORS) > 1 else 0
        self._timer = QTimer(self)
        self._timer.setInterval(self._TICK_MS)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()
        self.setMinimumSize(92, 92)

    def set_outline_mode(self, mode: str) -> None:
        if mode not in OUTLINE_MODES or mode == self._outline_mode:
            return
        self._outline_mode = mode
        self.update()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        self._timer.start()
        super().showEvent(event)

    def _on_tick(self) -> None:
        if len(FLAG_PREVIEW_COLORS) <= 1:
            return
        cycle_length = self._HOLD_MS + self._FADE_MS
        self._phase_ms += self._TICK_MS
        if self._phase_ms >= cycle_length:
            self._phase_ms -= cycle_length
            self._current_index = self._next_index
            self._next_index = (self._next_index + 1) % len(FLAG_PREVIEW_COLORS)
        self.update()

    def _current_flag_color(self) -> dict[str, str] | None:
        if not FLAG_PREVIEW_COLORS:
            return None
        if len(FLAG_PREVIEW_COLORS) == 1:
            return FLAG_PREVIEW_COLORS[0]

        current = FLAG_PREVIEW_COLORS[self._current_index]
        if self._phase_ms < self._HOLD_MS:
            return current

        next_color = FLAG_PREVIEW_COLORS[self._next_index]
        progress = (self._phase_ms - self._HOLD_MS) / self._FADE_MS
        blended = _interpolate_color(
            flag_theme_qcolor(current, self._night_mode),
            flag_theme_qcolor(next_color, self._night_mode),
            progress,
        ).name()
        return {"light": blended, "dark": blended}

    def paintEvent(self, _event) -> None:
        rect = self.rect().adjusted(5, 5, -5, -5)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self._night_mode:
            background = QColor("#2A2E33")
            border = QColor("#444A50")
        else:
            background = QColor("#F8F9FA")
            border = QColor("#D2D7DC")

        painter.setPen(QPen(border, 1))
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 8, 8)

        flag_color = self._current_flag_color()
        if flag_color is None:
            return

        fill = flag_theme_qcolor(flag_color, self._night_mode)
        outline = outline_color_for_mode(
            self._outline_mode, flag_color, self._night_mode
        )
        font = QFont(self.font())
        font.setPixelSize(int(min(rect.width(), rect.height()) * 0.62))
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(FLAG_GLYPH)
        x = rect.left() + (rect.width() - text_width) // 2
        y = rect.top() + (rect.height() + metrics.ascent() - metrics.descent()) // 2
        path = QPainterPath()
        path.addText(x, y, font, FLAG_GLYPH)

        painter.setPen(QPen(outline, 1.2))
        painter.setBrush(fill)
        painter.drawPath(path)


def open_settings_dialog() -> None:
    if aqt.mw is None:
        return
    dialog = FlagColumnSettingsDialog(aqt.mw)
    dialog.exec()


def setup_config_menu() -> None:
    if aqt.mw is None:
        return
    if getattr(aqt.mw, "_flag_column_config_action", None) is not None:
        return
    action = aqt.mw.form.menuTools.addAction("Flag Column Settings...")
    action.triggered.connect(open_settings_dialog)
    aqt.mw._flag_column_config_action = action


def _interpolate_color(start: QColor, end: QColor, progress: float) -> QColor:
    progress = min(max(progress, 0.0), 1.0)
    inverse = 1.0 - progress
    return QColor(
        round(start.red() * inverse + end.red() * progress),
        round(start.green() * inverse + end.green() * progress),
        round(start.blue() * inverse + end.blue() * progress),
        round(start.alpha() * inverse + end.alpha() * progress),
    )

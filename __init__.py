from __future__ import annotations

__name__ = "Flag Column in Browser"
__author__ = "Qaisar"
__version__ = "1.1"
__description__ = "Shows a flag indicator column in the Anki Browser."

import aqt
from anki.collection import BrowserColumns as Columns
from anki.consts import (
    QUEUE_TYPE_MANUALLY_BURIED,
    QUEUE_TYPE_SIBLING_BURIED,
    QUEUE_TYPE_SUSPENDED,
)
from anki.errors import NotFoundError
from aqt import colors, gui_hooks
from aqt.browser.table import Column, StatusDelegate, adjusted_bg_color
from aqt.qt import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFont,
    QFontMetrics,
    QHeaderView,
    QColor,
    QLabel,
    QModelIndex,
    QPainter,
    QPainterPath,
    QPen,
    QRadioButton,
    QStyleOptionViewItem,
    QVBoxLayout,
    Qt,
)
from aqt.theme import theme_manager

_FLAG_COLOR_BY_INDEX = {
    1: colors.FLAG_1,
    2: colors.FLAG_2,
    3: colors.FLAG_3,
    4: colors.FLAG_4,
    5: colors.FLAG_5,
    6: colors.FLAG_6,
    7: colors.FLAG_7,
}

_FLAG_COLUMN_KEY = "_flag_indicator"
_FLAG_COLUMN_WIDTH = 21
_FLAG_GLYPH = "⚑"
_OUTLINE_CONFIG_KEY = "flag_outline"
_OUTLINE_MODE_AUTO = "auto"
_OUTLINE_MODE_BLACK = "black"
_OUTLINE_MODE_WHITE = "white"
_OUTLINE_MODE_FLAG = "flag"
_OUTLINE_MODES = {
    _OUTLINE_MODE_AUTO,
    _OUTLINE_MODE_BLACK,
    _OUTLINE_MODE_WHITE,
    _OUTLINE_MODE_FLAG,
}
_OUTLINE_MODE = _OUTLINE_MODE_AUTO


def _addon_module_name() -> str:
    spec = globals().get("__spec__")
    if spec is not None and getattr(spec, "name", None):
        return spec.name
    return __name__


def _load_outline_mode() -> None:
    global _OUTLINE_MODE
    if aqt.mw is None:
        _OUTLINE_MODE = _OUTLINE_MODE_AUTO
        return
    config = aqt.mw.addonManager.getConfig(_addon_module_name()) or {}
    mode = config.get(_OUTLINE_CONFIG_KEY, _OUTLINE_MODE_AUTO)
    if mode not in _OUTLINE_MODES:
        mode = _OUTLINE_MODE_AUTO
    _OUTLINE_MODE = mode


def _save_outline_mode(mode: str) -> None:
    global _OUTLINE_MODE
    if mode not in _OUTLINE_MODES:
        return
    _OUTLINE_MODE = mode
    if aqt.mw is None:
        return
    config = aqt.mw.addonManager.getConfig(_addon_module_name()) or {}
    if config.get(_OUTLINE_CONFIG_KEY) == mode:
        return
    config[_OUTLINE_CONFIG_KEY] = mode
    aqt.mw.addonManager.writeConfig(_addon_module_name(), config)


def _outline_color(flag_color: dict[str, str] | None) -> QColor | Qt.GlobalColor:
    if _OUTLINE_MODE == _OUTLINE_MODE_BLACK:
        return Qt.GlobalColor.black
    if _OUTLINE_MODE == _OUTLINE_MODE_WHITE:
        return Qt.GlobalColor.white
    if _OUTLINE_MODE == _OUTLINE_MODE_FLAG and flag_color is not None:
        return theme_manager.qcolor(flag_color)
    return Qt.GlobalColor.white if theme_manager.night_mode else Qt.GlobalColor.black


def _refresh_browser_view() -> None:
    if aqt.mw is None:
        return
    browser = getattr(aqt.mw, "browser", None)
    if browser is None:
        return
    view = getattr(browser.table, "_view", None)
    if view is None:
        return
    view.viewport().update()


class FlagOutlineConfigDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Flag Column Settings")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Flag outline color"))

        self._buttons: dict[str, QRadioButton] = {}
        self._group = QButtonGroup(self)
        for label, mode in (
            ("Auto (match theme)", _OUTLINE_MODE_AUTO),
            ("Always black", _OUTLINE_MODE_BLACK),
            ("Always white", _OUTLINE_MODE_WHITE),
            ("Match flag color", _OUTLINE_MODE_FLAG),
        ):
            button = QRadioButton(label)
            self._group.addButton(button)
            self._buttons[mode] = button
            layout.addWidget(button)

        current = _OUTLINE_MODE if _OUTLINE_MODE in _OUTLINE_MODES else _OUTLINE_MODE_AUTO
        self._buttons[current].setChecked(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _selected_mode(self) -> str:
        for mode, button in self._buttons.items():
            if button.isChecked():
                return mode
        return _OUTLINE_MODE_AUTO

    def accept(self) -> None:
        _save_outline_mode(self._selected_mode())
        _refresh_browser_view()
        super().accept()


def _color_key(color: dict[str, str] | None) -> tuple[str | None, str | None] | None:
    if not color:
        return None
    return (color.get("light"), color.get("dark"))


_FLAG_BG_KEYS = {
    key
    for key in (
        _color_key(adjusted_bg_color(colors.FLAG_1)),
        _color_key(adjusted_bg_color(colors.FLAG_2)),
        _color_key(adjusted_bg_color(colors.FLAG_3)),
        _color_key(adjusted_bg_color(colors.FLAG_4)),
        _color_key(adjusted_bg_color(colors.FLAG_5)),
        _color_key(adjusted_bg_color(colors.FLAG_6)),
        _color_key(adjusted_bg_color(colors.FLAG_7)),
    )
    if key is not None
}

_STATE_BG_COLORS = {
    "marked": adjusted_bg_color(colors.STATE_MARKED),
    "suspended": adjusted_bg_color(colors.STATE_SUSPENDED),
    "buried": adjusted_bg_color(colors.STATE_BURIED),
}


def _row_base_color(card) -> dict[str, str] | None:
    try:
        note = card.note()
    except NotFoundError:
        return None
    if note.has_tag("marked"):
        return _STATE_BG_COLORS["marked"]
    if card.queue == QUEUE_TYPE_SUSPENDED:
        return _STATE_BG_COLORS["suspended"]
    if card.queue in (QUEUE_TYPE_MANUALLY_BURIED, QUEUE_TYPE_SIBLING_BURIED):
        return _STATE_BG_COLORS["buried"]
    return None


def _flag_color(flag_index: int):
    return _FLAG_COLOR_BY_INDEX.get(flag_index)


class FlagIconDelegate(StatusDelegate):
    def paint(
        self, painter: QPainter | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        super().paint(painter, option, index)

        if self._model.column_at(index).key != _FLAG_COLUMN_KEY:
            return
        row = self._model.get_row(index)
        flag_index = getattr(row, "_flag_indicator", 0)
        if not flag_index or painter is None:
            return
        flag_color = _flag_color(flag_index)
        if flag_color is None:
            return
        rect = option.rect
        size = min(16, rect.height() - 2)
        if size <= 0:
            return
        font = QFont(option.font)
        font.setPixelSize(size)
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(_FLAG_GLYPH)
        x = rect.left() + (rect.width() - text_width) // 2
        y = rect.top() + (rect.height() + metrics.ascent() - metrics.descent()) // 2
        path = QPainterPath()
        path.addText(x, y, font, _FLAG_GLYPH)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        outline = _outline_color(flag_color)
        painter.setPen(QPen(outline, 1))
        painter.setBrush(theme_manager.qcolor(flag_color))
        painter.drawPath(path)
        painter.restore()


def _on_browser_did_fetch_columns(columns: dict[str, Column]) -> None:
    if _FLAG_COLUMN_KEY in columns:
        return
    columns[_FLAG_COLUMN_KEY] = Column(
        key=_FLAG_COLUMN_KEY,
        cards_mode_label=_FLAG_GLYPH,
        notes_mode_label=_FLAG_GLYPH,
        sorting_cards=Columns.SORTING_NONE,
        sorting_notes=Columns.SORTING_NONE,
        uses_cell_font=False,
        alignment=Columns.ALIGNMENT_CENTER,
        cards_mode_tooltip=f"{_FLAG_GLYPH} Flagged cards",
        notes_mode_tooltip=f"{_FLAG_GLYPH} Flagged notes",
    )


def _on_browser_did_fetch_row(card_or_note_id, is_note, row, columns) -> None:
    row._flag_indicator = 0
    if is_note:
        return
    if _color_key(row.color) not in _FLAG_BG_KEYS:
        return
    if aqt.mw is None or aqt.mw.col is None:
        return
    try:
        card = aqt.mw.col.get_card(card_or_note_id)
    except NotFoundError:
        return
    row._flag_indicator = card.user_flag()
    row.color = _row_base_color(card)


def _on_browser_will_show(browser) -> None:
    view = browser.table._view
    if view is None:
        return
    model = browser.table._model
    if model.active_column_index(_FLAG_COLUMN_KEY) is None:
        model.toggle_column(_FLAG_COLUMN_KEY)
    delegate = getattr(browser, "_flag_icon_delegate", None)
    if delegate is None:
        delegate = FlagIconDelegate(browser, model)
        browser._flag_icon_delegate = delegate
    view.setItemDelegate(delegate)

    header = view.horizontalHeader()
    if header is None:
        return
    column = model.active_column_index(_FLAG_COLUMN_KEY)
    if column is None:
        return
    visual = header.visualIndex(column)
    if visual != 0:
        header.moveSection(visual, 0)
    if header.minimumSectionSize() > _FLAG_COLUMN_WIDTH:
        header.setMinimumSectionSize(_FLAG_COLUMN_WIDTH)
    header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
    view.setColumnWidth(column, _FLAG_COLUMN_WIDTH)


def _open_config_dialog() -> None:
    if aqt.mw is None:
        return
    dialog = FlagOutlineConfigDialog(aqt.mw)
    dialog.exec()


def _setup_config_menu() -> None:
    if aqt.mw is None:
        return
    if getattr(aqt.mw, "_flag_column_config_action", None) is not None:
        return
    action = aqt.mw.form.menuTools.addAction("Flag Column Settings...")
    action.triggered.connect(_open_config_dialog)
    aqt.mw._flag_column_config_action = action


def _on_config_updated(*_args, **_kwargs) -> None:
    _load_outline_mode()
    _refresh_browser_view()


def _on_profile_did_open() -> None:
    _load_outline_mode()
    _setup_config_menu()
    if aqt.mw is None:
        return
    aqt.mw.addonManager.setConfigUpdatedAction(_addon_module_name(), _on_config_updated)


gui_hooks.browser_did_fetch_columns.append(_on_browser_did_fetch_columns)
gui_hooks.browser_will_show.append(_on_browser_will_show)
gui_hooks.browser_did_fetch_row.append(_on_browser_did_fetch_row)
gui_hooks.profile_did_open.append(_on_profile_did_open)

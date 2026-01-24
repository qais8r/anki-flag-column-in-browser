from __future__ import annotations

__name__ = "Flag Column in Browser"
__author__ = "Qaisar"
__version__ = "1.0"
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
    QFont,
    QFontMetrics,
    QHeaderView,
    QModelIndex,
    QPainter,
    QPainterPath,
    QPen,
    QStyleOptionViewItem,
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
        outline = Qt.GlobalColor.white if theme_manager.night_mode else Qt.GlobalColor.black
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


gui_hooks.browser_did_fetch_columns.append(_on_browser_did_fetch_columns)
gui_hooks.browser_will_show.append(_on_browser_will_show)
gui_hooks.browser_did_fetch_row.append(_on_browser_did_fetch_row)

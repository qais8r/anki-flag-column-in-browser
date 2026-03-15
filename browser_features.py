from __future__ import annotations

import aqt
from anki.collection import BrowserColumns as Columns
from anki.consts import (
    QUEUE_TYPE_MANUALLY_BURIED,
    QUEUE_TYPE_SIBLING_BURIED,
    QUEUE_TYPE_SUSPENDED,
)
from aqt import colors, gui_hooks
from aqt.browser.table import Column, StatusDelegate, adjusted_bg_color
from aqt.qt import (
    QFont,
    QColor,
    QHeaderView,
    QModelIndex,
    QPainter,
    QPainterPath,
    QPen,
    QRect,
    QRectF,
    QStyleOptionViewItem,
    Qt,
)
from aqt.theme import theme_manager

from .addon_config import (
    OUTLINE_MODE_BLACK,
    OUTLINE_MODE_FLAG,
    OUTLINE_MODE_WHITE,
    get_settings,
)

FLAG_GLYPH = "⚑"
FLAG_PREVIEW_COLORS = (
    colors.FLAG_1,
    colors.FLAG_2,
    colors.FLAG_3,
    colors.FLAG_4,
    colors.FLAG_5,
    colors.FLAG_6,
    colors.FLAG_7,
)

_FLAG_COLOR_BY_INDEX = {
    index: color for index, color in enumerate(FLAG_PREVIEW_COLORS, start=1)
}
_FLAG_COLUMN_KEY = "_flag_indicator"
_FLAG_COLUMN_WIDTH = 21
_SORT_FIELD_COLUMN_KEY = "noteFld"
_STATE_MARKED = "marked"
_STATE_SUSPENDED = "suspended"
_STATE_BURIED = "buried"
_STATE_SYMBOL_SUSPENDED = "!"
_STATE_SYMBOL_MARKED = "✱"
_STATE_SYMBOL_BURIED = "→"
_STATE_BADGE_MARGIN = 4
_STATE_BADGE_SPACING = 3
_STATE_TEXT_GAP = 0
_CARD_STATE_SQL = """
select
  c.queue,
  instr(' ' || lower(coalesce(n.tags, '')) || ' ', ' marked ') > 0
from cards c
join notes n on n.id = c.nid
where c.id = ?
"""
_HOOKS_INSTALLED = False


def flag_theme_qcolor(flag_color: dict[str, str] | None, night_mode: bool) -> QColor:
    if flag_color is None:
        return QColor()
    key = "dark" if night_mode else "light"
    color = flag_color.get(key) or flag_color.get("light") or flag_color.get("dark")
    return QColor(color) if color else QColor()


def outline_color_for_mode(
    mode: str, flag_color: dict[str, str] | None, night_mode: bool
) -> QColor | Qt.GlobalColor:
    if mode == OUTLINE_MODE_BLACK:
        return Qt.GlobalColor.black
    if mode == OUTLINE_MODE_WHITE:
        return Qt.GlobalColor.white
    if mode == OUTLINE_MODE_FLAG and flag_color is not None:
        return flag_theme_qcolor(flag_color, night_mode)
    return Qt.GlobalColor.white if night_mode else Qt.GlobalColor.black


def refresh_browser_view(force_refetch: bool = False) -> None:
    if aqt.mw is None:
        return
    browser = getattr(aqt.mw, "browser", None)
    if browser is None:
        return

    table = getattr(browser, "table", None)
    if table is None:
        return

    if force_refetch:
        model = getattr(table, "_model", None)
        if model is not None:
            model.mark_cache_stale()
        table.redraw_cells()
        return

    view = getattr(table, "_view", None)
    if view is not None:
        view.viewport().update()


def install_hooks() -> None:
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return
    gui_hooks.browser_did_fetch_columns.append(_on_browser_did_fetch_columns)
    gui_hooks.browser_will_show.append(_on_browser_will_show)
    gui_hooks.browser_did_fetch_row.append(_on_browser_did_fetch_row)
    _HOOKS_INSTALLED = True


def _outline_color(flag_color: dict[str, str] | None) -> QColor | Qt.GlobalColor:
    settings = get_settings()
    if settings.outline_mode == OUTLINE_MODE_FLAG and flag_color is not None:
        return theme_manager.qcolor(flag_color)
    return outline_color_for_mode(
        settings.outline_mode, flag_color, theme_manager.night_mode
    )


def _color_key(color: dict[str, str] | None) -> tuple[str | None, str | None] | None:
    if not color:
        return None
    return (color.get("light"), color.get("dark"))


_FLAG_INDEX_BY_BG_KEY = {
    key: index
    for index, color in _FLAG_COLOR_BY_INDEX.items()
    if (key := _color_key(adjusted_bg_color(color))) is not None
}
_MARKED_BG_KEY = _color_key(adjusted_bg_color(colors.STATE_MARKED))
_SUSPENDED_BG_KEY = _color_key(adjusted_bg_color(colors.STATE_SUSPENDED))
_BURIED_BG_KEY = _color_key(adjusted_bg_color(colors.STATE_BURIED))
_STATE_BG_COLORS = {
    _STATE_MARKED: adjusted_bg_color(colors.STATE_MARKED),
    _STATE_SUSPENDED: adjusted_bg_color(colors.STATE_SUSPENDED),
    _STATE_BURIED: adjusted_bg_color(colors.STATE_BURIED),
}
_STATE_BADGE_TEXT = {
    _STATE_MARKED: _STATE_SYMBOL_MARKED,
    _STATE_SUSPENDED: _STATE_SYMBOL_SUSPENDED,
    _STATE_BURIED: _STATE_SYMBOL_BURIED,
}
_STATE_ICON_COLORS = {
    _STATE_MARKED: colors.STATE_MARKED,
    _STATE_SUSPENDED: colors.STATE_SUSPENDED,
    _STATE_BURIED: colors.STATE_BURIED,
}


def _lookup_card_state(card_id: int) -> tuple[int, bool] | None:
    if aqt.mw is None or aqt.mw.col is None:
        return None
    row = aqt.mw.col.db.first(_CARD_STATE_SQL, card_id)
    if row is None:
        return None
    queue, is_marked = row
    return int(queue), bool(is_marked)


def _base_color_for_state(queue: int, is_marked: bool) -> dict[str, str] | None:
    if is_marked:
        return _STATE_BG_COLORS[_STATE_MARKED]
    if queue == QUEUE_TYPE_SUSPENDED:
        return _STATE_BG_COLORS[_STATE_SUSPENDED]
    if queue in (QUEUE_TYPE_MANUALLY_BURIED, QUEUE_TYPE_SIBLING_BURIED):
        return _STATE_BG_COLORS[_STATE_BURIED]
    return None


def _state_badges(queue: int, is_marked: bool) -> tuple[str, ...]:
    states: list[str] = []
    if queue == QUEUE_TYPE_SUSPENDED:
        states.append(_STATE_SUSPENDED)
    if is_marked:
        states.append(_STATE_MARKED)
    if queue in (QUEUE_TYPE_MANUALLY_BURIED, QUEUE_TYPE_SIBLING_BURIED):
        states.append(_STATE_BURIED)
    return tuple(states)


def _sort_field_index(columns: list[str]) -> int | None:
    try:
        return columns.index(_SORT_FIELD_COLUMN_KEY)
    except ValueError:
        return None


def _display_state(color_key: tuple[str | None, str | None] | None) -> tuple[int, bool]:
    if color_key == _MARKED_BG_KEY:
        return 0, True
    if color_key == _SUSPENDED_BG_KEY:
        return QUEUE_TYPE_SUSPENDED, False
    if color_key == _BURIED_BG_KEY:
        return QUEUE_TYPE_MANUALLY_BURIED, False
    return 0, False


def _flag_color(flag_index: int) -> dict[str, str] | None:
    return _FLAG_COLOR_BY_INDEX.get(flag_index)


def _state_icon_fill(state: str) -> QColor:
    color = _STATE_ICON_COLORS.get(state)
    return theme_manager.qcolor(color) if color is not None else QColor("#9099A5")


def _badge_text_color(fill: QColor) -> QColor:
    luminance = 0.2126 * fill.red() + 0.7152 * fill.green() + 0.0722 * fill.blue()
    return QColor("#111111") if luminance > 150 else QColor("#F7F9FB")


def _state_badge_text(state: str) -> str:
    return _STATE_BADGE_TEXT.get(state, "?")


class FlagIconDelegate(StatusDelegate):
    def __init__(self, browser, model) -> None:
        super().__init__(browser, model)
        self._glyph_cache: dict[str, tuple[QPainterPath, QRectF]] = {}

    def _glyph_path(
        self, base_font: QFont, pixel_size: int
    ) -> tuple[QPainterPath, QRectF]:
        font = QFont(base_font)
        font.setPixelSize(pixel_size)
        key = font.toString()
        cached = self._glyph_cache.get(key)
        if cached is not None:
            return cached
        path = QPainterPath()
        path.addText(0, 0, font, FLAG_GLYPH)
        cached = (path, path.boundingRect())
        self._glyph_cache[key] = cached
        return cached

    def paint(
        self, painter: QPainter | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        column_key = self._model.column_at(index).key
        if column_key == _SORT_FIELD_COLUMN_KEY and self._paint_sort_field_badges(
            painter, option, index
        ):
            return

        super().paint(painter, option, index)

        if column_key != _FLAG_COLUMN_KEY:
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

        path, bounds = self._glyph_path(option.font, size)
        center = rect.center()
        x = center.x() - bounds.center().x()
        y = center.y() - bounds.center().y()

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(_outline_color(flag_color), 1))
        painter.setBrush(theme_manager.qcolor(flag_color))
        painter.translate(x, y)
        painter.drawPath(path)
        painter.restore()

    def _paint_sort_field_badges(
        self, painter: QPainter | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> bool:
        if painter is None:
            return False

        row = self._model.get_row(index)
        badges = getattr(row, "_state_badges", ())
        if not badges:
            return False

        cell = self._model.get_cell(index)
        paint_option = QStyleOptionViewItem(option)
        paint_option.textElideMode = cell.elide_mode
        if cell.is_rtl:
            paint_option.direction = Qt.LayoutDirection.RightToLeft

        if row_color := row.color:
            painter.save()
            painter.fillRect(paint_option.rect, theme_manager.qcolor(row_color))
            painter.restore()

        self.drawBackground(painter, paint_option, index)
        badges_rect, text_rect = self._layout_sort_field_rects(
            paint_option.rect, len(badges), cell.is_rtl
        )
        self._draw_state_badges(painter, badges_rect, badges, cell.is_rtl)
        self.drawDisplay(painter, paint_option, text_rect, cell.text)
        self.drawFocus(painter, paint_option, paint_option.rect)
        return True

    def _layout_sort_field_rects(
        self, rect: QRect, badge_count: int, is_rtl: bool
    ) -> tuple[QRect, QRect]:
        badge_size = max(12, min(16, rect.height() - 6))
        total_width = badge_size * badge_count + _STATE_BADGE_SPACING * (badge_count - 1)
        badges_width = _STATE_BADGE_MARGIN + total_width + _STATE_TEXT_GAP
        badges_rect = QRect(rect)
        text_rect = QRect(rect)

        if is_rtl:
            badges_rect.setLeft(rect.right() - badges_width + 1)
            text_rect.setRight(rect.right() - badges_width)
        else:
            badges_rect.setWidth(badges_width)
            text_rect.setLeft(rect.left() + badges_width)
        return badges_rect, text_rect

    def _draw_state_badges(
        self, painter: QPainter, rect: QRect, badges: tuple[str, ...], is_rtl: bool
    ) -> None:
        if not badges:
            return

        badge_size = max(12, min(16, rect.height() - 6))
        total_width = badge_size * len(badges) + _STATE_BADGE_SPACING * (len(badges) - 1)
        badge_y = rect.top() + max(1, (rect.height() - badge_size) // 2)
        if is_rtl:
            start_x = rect.right() - total_width - _STATE_BADGE_MARGIN + 1
        else:
            start_x = rect.left() + _STATE_BADGE_MARGIN

        base_font = QFont(painter.font())
        base_font.setBold(True)
        base_font.setPixelSize(max(8, badge_size - 5))

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for idx, state in enumerate(badges):
            badge_x = start_x + idx * (badge_size + _STATE_BADGE_SPACING)
            fill = _state_icon_fill(state)
            text = _state_badge_text(state)
            text_color = _badge_text_color(fill)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(badge_x, badge_y, badge_size, badge_size, 2.5, 2.5)

            symbol_font = QFont(base_font)
            if state == _STATE_MARKED:
                symbol_font.setPixelSize(max(10, badge_size - 1))
            elif state == _STATE_BURIED:
                symbol_font.setPixelSize(max(9, badge_size - 3))
            painter.setFont(symbol_font)
            painter.setPen(QPen(text_color, 1))
            painter.drawText(
                badge_x,
                badge_y,
                badge_size,
                badge_size,
                Qt.AlignmentFlag.AlignCenter,
                text,
            )
        painter.restore()


def _on_browser_did_fetch_columns(columns: dict[str, Column]) -> None:
    if _FLAG_COLUMN_KEY in columns:
        return
    columns[_FLAG_COLUMN_KEY] = Column(
        key=_FLAG_COLUMN_KEY,
        cards_mode_label=FLAG_GLYPH,
        notes_mode_label=FLAG_GLYPH,
        sorting_cards=Columns.SORTING_NONE,
        sorting_notes=Columns.SORTING_NONE,
        uses_cell_font=False,
        alignment=Columns.ALIGNMENT_CENTER,
        cards_mode_tooltip=f"{FLAG_GLYPH} Flagged cards",
        notes_mode_tooltip=f"{FLAG_GLYPH} Flagged notes",
    )


def _on_browser_did_fetch_row(card_or_note_id, is_note, row, columns) -> None:
    row._flag_indicator = 0
    row._state_badges = ()
    if is_note:
        return

    settings = get_settings()
    sort_field_index = (
        _sort_field_index(columns)
        if settings.show_state_prefixes_in_sort_field
        else None
    )
    color_key = _color_key(row.color)
    flag_index = _FLAG_INDEX_BY_BG_KEY.get(color_key, 0)
    if flag_index:
        row._flag_indicator = flag_index

    queue, is_marked = _display_state(color_key)
    needs_lookup = bool(flag_index) or (
        sort_field_index is not None and color_key == _MARKED_BG_KEY
    )
    if needs_lookup:
        state = _lookup_card_state(card_or_note_id)
        if state is not None:
            queue, is_marked = state
        elif flag_index:
            queue, is_marked = 0, False

    if flag_index:
        row.color = _base_color_for_state(queue, is_marked)
    if sort_field_index is not None:
        row._state_badges = _state_badges(queue, is_marked)


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

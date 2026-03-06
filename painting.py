from __future__ import annotations

from aqt.browser.table import StatusDelegate
from aqt.qt import (
    QFont,
    QFontMetrics,
    QIcon,
    QColor,
    QModelIndex,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QSize,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    Qt,
)
from aqt.theme import theme_manager

from .config import AddonSettings, get_settings
from .constants import (
    FLAG_COLUMN_KEY,
    FLAG_GLYPH,
    PREVIEW_FLAG_COLUMN,
    PREVIEW_ROLE_FLAG,
    PREVIEW_ROLE_STATES,
    PREVIEW_STATE_COLUMN,
    SELECTION_STYLE_BORDER,
    SELECTION_STYLE_CLASSIC,
    STATE_BURIED,
    STATE_MARKED,
    STATE_COLUMN_KEY,
)
from .row_state import (
    badge_text_color,
    flag_color,
    outline_qcolor,
    state_icon_fill,
    state_badge_text,
    theme_qcolor,
)


def draw_flag_glyph(
    painter: QPainter,
    rect,
    flag_index: int,
    *,
    outline_mode: str,
    flag_border_enabled: bool,
) -> None:
    if flag_index <= 0:
        return

    color = flag_color(flag_index)
    if color is None:
        return

    size = min(16, rect.height() - 2)
    if size <= 0:
        return

    font = QFont(painter.font())
    font.setPixelSize(size)
    metrics = QFontMetrics(font)
    text_width = metrics.horizontalAdvance(FLAG_GLYPH)
    baseline_x = rect.left() + (rect.width() - text_width) // 2
    baseline_y = rect.top() + (rect.height() + metrics.ascent() - metrics.descent()) // 2
    path = QPainterPath()
    path.addText(baseline_x, baseline_y, font, FLAG_GLYPH)

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    if flag_border_enabled:
        painter.setPen(QPen(outline_qcolor(outline_mode, color), 1))
    else:
        painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(theme_qcolor(color))
    painter.drawPath(path)
    painter.restore()


def draw_state_badges(painter: QPainter, rect, states: tuple[str, ...]) -> None:
    if not states:
        return

    count = len(states)
    spacing = 2
    badge_size = max(10, min(14, rect.height() - 6))
    total_width = badge_size * count + spacing * (count - 1)
    start_x = rect.left() + max(1, (rect.width() - total_width) // 2)
    badge_y = rect.top() + max(1, (rect.height() - badge_size) // 2)

    base_font = QFont(painter.font())
    base_font.setBold(True)
    base_font.setPixelSize(max(8, badge_size - 5))

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    for idx, state in enumerate(states):
        badge_x = start_x + idx * (badge_size + spacing)
        fill = state_icon_fill(state)
        text = state_badge_text(state)
        text_color = badge_text_color(fill)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(badge_x, badge_y, badge_size, badge_size, 2.5, 2.5)

        symbol_font = QFont(base_font)
        if state == STATE_MARKED:
            symbol_font.setPixelSize(max(10, badge_size - 1))
        elif state == STATE_BURIED:
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


def outline_mode_tile_icon(mode: str, size: QSize = QSize(90, 56)) -> QIcon:
    dpr = 1.0
    pixel_size = QSize(size)
    pixmap = QPixmap(pixel_size)
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    night_mode = theme_manager.night_mode
    card_bg = QColor("#2A3038") if night_mode else QColor("#F3F6FA")
    card_border = QColor("#444B55") if night_mode else QColor("#C5CDD8")
    outer = pixmap.rect().adjusted(3, 3, -3, -3)
    painter.setPen(QPen(card_border, 1))
    painter.setBrush(card_bg)
    painter.drawRoundedRect(outer, 8, 8)

    color = flag_color(4)
    if color is not None:
        glyph_rect = outer.adjusted(0, 0, -1, -1)
        draw_flag_glyph(
            painter,
            glyph_rect,
            4,
            outline_mode=mode,
            flag_border_enabled=True,
        )

    painter.end()
    return QIcon(pixmap)


def selection_style_tile_icon(
    selection_style: str, size: QSize = QSize(110, 42)
) -> QIcon:
    pixmap = QPixmap(size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    night_mode = theme_manager.night_mode
    card_bg = QColor("#2A3038") if night_mode else QColor("#F8FAFD")
    card_border = QColor("#444B55") if night_mode else QColor("#C5CDD8")
    row_bg = QColor("#343C47") if night_mode else QColor("#FFFFFF")
    selected_blue = QColor("#5BA8FF") if night_mode else QColor("#66B5FF")
    border_blue = QColor("#67C8FF") if night_mode else QColor("#20A7F7")

    outer = pixmap.rect().adjusted(3, 3, -3, -3)
    painter.setPen(QPen(card_border, 1))
    painter.setBrush(card_bg)
    painter.drawRoundedRect(outer, 7, 7)

    row_rect = outer.adjusted(6, 10, -6, -10)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(row_bg)
    painter.drawRoundedRect(row_rect, 4, 4)

    if selection_style == SELECTION_STYLE_CLASSIC:
        painter.setBrush(selected_blue)
        painter.drawRoundedRect(row_rect, 4, 4)
    else:
        painter.setPen(QPen(border_blue, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(row_rect.adjusted(0, 0, -1, -1), 4, 4)

    painter.end()
    return QIcon(pixmap)


def _row_is_selected(
    option: QStyleOptionViewItem, index: QModelIndex
) -> bool:
    view = option.widget
    selection = view.selectionModel() if view is not None else None
    if selection is not None:
        return selection.isRowSelected(index.row(), QModelIndex())
    return bool(option.state & QStyle.StateFlag.State_Selected)


class BrowserStatusDelegate(StatusDelegate):
    def paint(
        self, painter: QPainter | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        settings = get_settings()
        paint_option = QStyleOptionViewItem(option)
        if settings.selection_style == SELECTION_STYLE_BORDER and _row_is_selected(
            option, index
        ):
            # Keep Anki's state row backgrounds visible and paint the border in an overlay.
            paint_option.state &= ~QStyle.StateFlag.State_Selected

        super().paint(painter, paint_option, index)
        if painter is None:
            return

        column_key = self._model.column_at(index).key
        row = self._model.get_row(index)
        if column_key == FLAG_COLUMN_KEY:
            draw_flag_glyph(
                painter,
                option.rect,
                getattr(row, FLAG_COLUMN_KEY, 0),
                outline_mode=settings.outline_mode,
                flag_border_enabled=settings.flag_border_enabled,
            )
        elif column_key == STATE_COLUMN_KEY and settings.state_icons_enabled:
            draw_state_badges(painter, option.rect, getattr(row, STATE_COLUMN_KEY, ()))


class PreviewDelegate(QStyledItemDelegate):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._settings = AddonSettings()

    def set_settings(self, settings: AddonSettings) -> None:
        self._settings = settings

    def paint(
        self, painter: QPainter | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        if painter is None:
            return

        paint_option = QStyleOptionViewItem(option)
        if self._settings.selection_style == SELECTION_STYLE_BORDER and _row_is_selected(
            option, index
        ):
            paint_option.state &= ~QStyle.StateFlag.State_Selected
        super().paint(painter, paint_option, index)

        if index.column() == PREVIEW_FLAG_COLUMN:
            draw_flag_glyph(
                painter,
                option.rect,
                index.data(PREVIEW_ROLE_FLAG) or 0,
                outline_mode=self._settings.outline_mode,
                flag_border_enabled=self._settings.flag_border_enabled,
            )
        elif (
            index.column() == PREVIEW_STATE_COLUMN
            and self._settings.state_icons_enabled
        ):
            states = index.data(PREVIEW_ROLE_STATES)
            draw_state_badges(painter, option.rect, states if isinstance(states, tuple) else ())

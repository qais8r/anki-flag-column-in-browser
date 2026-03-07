from __future__ import annotations

from aqt.browser.table import StatusDelegate
from aqt.qt import (
    QFont,
    QFontMetrics,
    QGuiApplication,
    QIcon,
    QColor,
    QModelIndex,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRectF,
    QSize,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTableView,
    Qt,
)
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
    selection_border_qcolor,
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
    max_size: int = 16,
) -> None:
    if flag_index <= 0:
        return

    color = flag_color(flag_index)
    if color is None:
        return

    size = min(max_size, rect.height() - 2)
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


def _icon_pixmap(size: QSize) -> tuple[QPixmap, QPainter, QRectF]:
    app = QGuiApplication.instance()
    screen = app.primaryScreen() if app is not None else None
    dpr = max(1.0, float(screen.devicePixelRatio())) if screen is not None else 1.0
    pixel_size = QSize(
        max(1, round(size.width() * dpr)),
        max(1, round(size.height() * dpr)),
    )
    pixmap = QPixmap(pixel_size)
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    return pixmap, painter, QRectF(0, 0, size.width(), size.height())


def _draw_tile_surface(painter: QPainter, rect: QRectF, *, night_mode: bool) -> QRectF:
    frame_fill = QColor("#1E242C") if night_mode else QColor("#EDF2F7")
    frame_pen = QColor("#55606C") if night_mode else QColor("#C5CDD8")
    content_fill = QColor("#303945") if night_mode else QColor("#FFFFFF")

    painter.setPen(QPen(frame_pen, 1))
    painter.setBrush(frame_fill)
    painter.drawRoundedRect(rect, 7, 7)

    inner = rect.adjusted(5, 5, -5, -5)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(content_fill)
    painter.drawRoundedRect(inner, 6, 6)
    return inner


def _split_preview_rects(bounds: QRectF) -> tuple[QRectF, QRectF]:
    content = bounds.adjusted(1, 1, -1, -1)
    gap = 6
    panel_width = (content.width() - gap) / 2
    left = QRectF(content.left(), content.top(), panel_width, content.height())
    right = QRectF(left.right() + gap, content.top(), panel_width, content.height())
    return left, right


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
    pixmap, painter, bounds = _icon_pixmap(size)

    color = flag_color(4)
    if color is not None:
        for night_mode, panel in zip((False, True), _split_preview_rects(bounds)):
            glyph_rect = _draw_tile_surface(painter, panel, night_mode=night_mode)
            draw_flag_glyph(
                painter,
                glyph_rect.adjusted(0, 1, 0, 0).toRect(),
                4,
                outline_mode=mode,
                flag_border_enabled=True,
                max_size=24,
            )

    painter.end()
    return QIcon(pixmap)


def selection_style_tile_icon(
    selection_style: str, size: QSize = QSize(110, 42)
) -> QIcon:
    pixmap, painter, bounds = _icon_pixmap(size)

    for night_mode, panel in zip((False, True), _split_preview_rects(bounds)):
        inner = _draw_tile_surface(painter, panel, night_mode=night_mode)
        row_bg = QColor("#343C47") if night_mode else QColor("#FFFFFF")
        selected_blue = QColor("#5BA8FF") if night_mode else QColor("#66B5FF")
        border_blue = QColor("#67C8FF") if night_mode else QColor("#20A7F7")

        row_rect = inner.adjusted(4, 8, -4, -8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(row_bg)
        painter.drawRoundedRect(row_rect, 4, 4)

        if selection_style == SELECTION_STYLE_CLASSIC:
            painter.setBrush(selected_blue)
            painter.drawRoundedRect(row_rect, 4, 4)
        else:
            painter.setPen(QPen(border_blue, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(row_rect.adjusted(1, 1, -1, -1), 4, 4)

    painter.end()
    return QIcon(pixmap)


def _row_is_selected(
    option: QStyleOptionViewItem, index: QModelIndex
) -> bool:
    view = _view_from_option(option)
    selection = view.selectionModel() if view is not None else None
    if selection is not None:
        return selection.isRowSelected(index.row(), QModelIndex())
    return bool(option.state & QStyle.StateFlag.State_Selected)


def _view_from_option(option: QStyleOptionViewItem) -> QTableView | None:
    widget = option.widget
    while widget is not None:
        if isinstance(widget, QTableView):
            return widget
        widget = widget.parentWidget()
    return None


def _is_first_visible_column(view: QTableView, column: int) -> bool:
    for candidate in range(column - 1, -1, -1):
        if not view.isColumnHidden(candidate):
            return False
    return True


def _is_last_visible_column(
    view: QTableView, column: int, model_column_count: int
) -> bool:
    for candidate in range(column + 1, model_column_count):
        if not view.isColumnHidden(candidate):
            return False
    return True


def _preview_sticky_active(view: QTableView, settings: AddonSettings) -> bool:
    if not settings.sticky_columns_enabled:
        return False

    if view.objectName() == "flagFrozenColumnsView":
        return True

    bar = view.horizontalScrollBar()
    return bar is not None and bar.value() > 0


def _paint_preview_selection_border(
    painter: QPainter,
    option: QStyleOptionViewItem,
    index: QModelIndex,
    settings: AddonSettings,
) -> None:
    view = _view_from_option(option)
    if view is None:
        return

    model = index.model()
    if model is None:
        return

    rect = option.rect
    color = selection_border_qcolor()
    thickness = 3
    sticky_active = _preview_sticky_active(view, settings)
    is_frozen_view = view.objectName() == "flagFrozenColumnsView"
    first_visible = _is_first_visible_column(view, index.column())
    last_visible = _is_last_visible_column(view, index.column(), model.columnCount())

    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)

    if sticky_active:
        painter.fillRect(rect.left(), rect.top(), rect.width(), thickness, color)
        painter.fillRect(
            rect.left(),
            rect.bottom() - thickness + 1,
            rect.width(),
            thickness,
            color,
        )
        if is_frozen_view and first_visible:
            painter.fillRect(rect.left(), rect.top(), thickness, rect.height(), color)
        if not is_frozen_view and last_visible:
            painter.fillRect(
                rect.right() - thickness + 1,
                rect.top(),
                thickness,
                rect.height(),
                color,
            )
    else:
        painter.fillRect(rect.left(), rect.top(), rect.width(), thickness, color)
        painter.fillRect(
            rect.left(),
            rect.bottom() - thickness + 1,
            rect.width(),
            thickness,
            color,
        )
        if first_visible:
            painter.fillRect(rect.left(), rect.top(), thickness, rect.height(), color)
        if last_visible:
            painter.fillRect(
                rect.right() - thickness + 1,
                rect.top(),
                thickness,
                rect.height(),
                color,
            )

    painter.restore()


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
        self._draw_selection_border = False
        self._preview_selected_row: int | None = None

    def set_settings(self, settings: AddonSettings) -> None:
        self._settings = settings

    def set_draw_selection_border(self, enabled: bool) -> None:
        self._draw_selection_border = enabled

    def set_preview_selected_row(self, row: int | None) -> None:
        self._preview_selected_row = row

    def paint(
        self, painter: QPainter | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        if painter is None:
            return

        selected = self._preview_selected_row is not None and index.row() == self._preview_selected_row
        paint_option = QStyleOptionViewItem(option)
        if self._settings.selection_style == SELECTION_STYLE_BORDER and selected:
            paint_option.state &= ~QStyle.StateFlag.State_Selected
        elif self._settings.selection_style == SELECTION_STYLE_CLASSIC and selected:
            paint_option.state |= QStyle.StateFlag.State_Selected
        super().paint(painter, paint_option, index)
        if self._draw_selection_border and self._settings.selection_style == SELECTION_STYLE_BORDER and selected:
            _paint_preview_selection_border(painter, option, index, self._settings)

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

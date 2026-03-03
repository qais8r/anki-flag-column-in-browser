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
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QEvent,
    QFrame,
    QFont,
    QFontMetrics,
    QHBoxLayout,
    QHeaderView,
    QIcon,
    QColor,
    QItemSelectionModel,
    QLabel,
    QModelIndex,
    QPixmap,
    QObject,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QSize,
    QSizePolicy,
    QStandardItem,
    QStandardItemModel,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
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
_STATE_COLUMN_KEY = "_state_icons"
_STATE_COLUMN_WIDTH = 44
_FLAG_GLYPH = "⚑"
_OUTLINE_CONFIG_KEY = "flag_outline"
_FLAG_BORDER_CONFIG_KEY = "flag_border_enabled"
_SELECTION_STYLE_CONFIG_KEY = "selection_style"
_SELECTION_BORDER_LEGACY_CONFIG_KEY = "selection_border_enabled"
_STATE_ICONS_CONFIG_KEY = "state_icons_enabled"
_STICKY_COLUMNS_CONFIG_KEY = "sticky_columns_enabled"
_OUTLINE_MODE_AUTO = "auto"
_OUTLINE_MODE_BLACK = "black"
_OUTLINE_MODE_WHITE = "white"
_OUTLINE_MODE_FLAG = "flag"
_SELECTION_STYLE_CLASSIC = "classic"
_SELECTION_STYLE_BORDER = "border"
_SELECTION_STYLES = {
    _SELECTION_STYLE_CLASSIC,
    _SELECTION_STYLE_BORDER,
}
_OUTLINE_MODES = {
    _OUTLINE_MODE_AUTO,
    _OUTLINE_MODE_BLACK,
    _OUTLINE_MODE_WHITE,
    _OUTLINE_MODE_FLAG,
}
_OUTLINE_MODE = _OUTLINE_MODE_AUTO
_FLAG_BORDER_ENABLED = True
_SELECTION_STYLE = _SELECTION_STYLE_BORDER
_STATE_ICONS_ENABLED = True
_STICKY_COLUMNS_ENABLED = False

_STATE_MARKED = "marked"
_STATE_SUSPENDED = "suspended"
_STATE_BURIED = "buried"
_STATE_ORDER = (_STATE_MARKED, _STATE_SUSPENDED, _STATE_BURIED)
_STATE_BADGE_TEXT = {
    _STATE_MARKED: "✱",
    _STATE_SUSPENDED: "!",
    _STATE_BURIED: "→",
}


def _flag_theme_qcolor(flag_color: dict[str, str] | None, night_mode: bool) -> QColor:
    if flag_color is None:
        return QColor()
    key = "dark" if night_mode else "light"
    color = flag_color.get(key) or flag_color.get("light") or flag_color.get("dark")
    return QColor(color) if color else QColor()


def _outline_color_for_mode(
    mode: str, flag_color: dict[str, str] | None, night_mode: bool
) -> QColor | Qt.GlobalColor:
    if mode == _OUTLINE_MODE_BLACK:
        return Qt.GlobalColor.black
    if mode == _OUTLINE_MODE_WHITE:
        return Qt.GlobalColor.white
    if mode == _OUTLINE_MODE_FLAG and flag_color is not None:
        return _flag_theme_qcolor(flag_color, night_mode)
    return Qt.GlobalColor.white if night_mode else Qt.GlobalColor.black


def _addon_module_name() -> str:
    spec = globals().get("__spec__")
    if spec is not None and getattr(spec, "name", None):
        return spec.name
    return __name__


def _load_outline_mode() -> None:
    global _OUTLINE_MODE, _FLAG_BORDER_ENABLED, _SELECTION_STYLE, _STATE_ICONS_ENABLED
    global _STICKY_COLUMNS_ENABLED
    if aqt.mw is None:
        _OUTLINE_MODE = _OUTLINE_MODE_AUTO
        _FLAG_BORDER_ENABLED = True
        _SELECTION_STYLE = _SELECTION_STYLE_BORDER
        _STATE_ICONS_ENABLED = True
        _STICKY_COLUMNS_ENABLED = False
        return
    config = aqt.mw.addonManager.getConfig(_addon_module_name()) or {}
    mode = config.get(_OUTLINE_CONFIG_KEY, _OUTLINE_MODE_AUTO)
    if mode not in _OUTLINE_MODES:
        mode = _OUTLINE_MODE_AUTO
    _OUTLINE_MODE = mode
    flag_border_enabled = config.get(_FLAG_BORDER_CONFIG_KEY, True)
    _FLAG_BORDER_ENABLED = flag_border_enabled if isinstance(flag_border_enabled, bool) else True

    selection_style = config.get(_SELECTION_STYLE_CONFIG_KEY)
    if selection_style not in _SELECTION_STYLES:
        legacy = config.get(_SELECTION_BORDER_LEGACY_CONFIG_KEY, True)
        border_enabled = legacy if isinstance(legacy, bool) else True
        selection_style = _SELECTION_STYLE_BORDER if border_enabled else _SELECTION_STYLE_CLASSIC
    _SELECTION_STYLE = selection_style

    state_icons_enabled = config.get(_STATE_ICONS_CONFIG_KEY, True)
    _STATE_ICONS_ENABLED = state_icons_enabled if isinstance(state_icons_enabled, bool) else True
    sticky_columns_enabled = config.get(_STICKY_COLUMNS_CONFIG_KEY, False)
    _STICKY_COLUMNS_ENABLED = (
        sticky_columns_enabled if isinstance(sticky_columns_enabled, bool) else False
    )


def _save_settings(
    mode: str,
    *,
    flag_border_enabled: bool,
    selection_style: str,
    state_icons_enabled: bool,
    sticky_columns_enabled: bool,
) -> None:
    global _OUTLINE_MODE, _FLAG_BORDER_ENABLED, _SELECTION_STYLE, _STATE_ICONS_ENABLED
    global _STICKY_COLUMNS_ENABLED
    if mode not in _OUTLINE_MODES or selection_style not in _SELECTION_STYLES:
        return
    _OUTLINE_MODE = mode
    _FLAG_BORDER_ENABLED = flag_border_enabled
    _SELECTION_STYLE = selection_style
    _STATE_ICONS_ENABLED = state_icons_enabled
    _STICKY_COLUMNS_ENABLED = sticky_columns_enabled
    if aqt.mw is None:
        return
    config = aqt.mw.addonManager.getConfig(_addon_module_name()) or {}
    if (
        config.get(_OUTLINE_CONFIG_KEY) == mode
        and config.get(_FLAG_BORDER_CONFIG_KEY) == flag_border_enabled
        and config.get(_SELECTION_STYLE_CONFIG_KEY) == selection_style
        and config.get(_STATE_ICONS_CONFIG_KEY) == state_icons_enabled
        and config.get(_STICKY_COLUMNS_CONFIG_KEY) == sticky_columns_enabled
    ):
        return
    config[_OUTLINE_CONFIG_KEY] = mode
    config[_FLAG_BORDER_CONFIG_KEY] = flag_border_enabled
    config[_SELECTION_STYLE_CONFIG_KEY] = selection_style
    config[_STATE_ICONS_CONFIG_KEY] = state_icons_enabled
    config[_STICKY_COLUMNS_CONFIG_KEY] = sticky_columns_enabled
    aqt.mw.addonManager.writeConfig(_addon_module_name(), config)


def _outline_color(flag_color: dict[str, str] | None) -> QColor | Qt.GlobalColor:
    if _OUTLINE_MODE == _OUTLINE_MODE_FLAG and flag_color is not None:
        return theme_manager.qcolor(flag_color)
    return _outline_color_for_mode(_OUTLINE_MODE, flag_color, theme_manager.night_mode)


def _refresh_browser_view() -> None:
    if aqt.mw is None:
        return
    browser = getattr(aqt.mw, "browser", None)
    if browser is None:
        return
    view = getattr(browser.table, "_view", None)
    if view is None:
        return
    _configure_browser_table(browser)
    refresh = getattr(browser.table, "refresh", None)
    if callable(refresh):
        refresh()
    else:
        view.viewport().update()


def _outline_mode_tile_icon(mode: str, size: QSize = QSize(90, 56)) -> QIcon:
    dpr = 1.0
    if aqt.mw is not None:
        try:
            dpr = max(1.0, float(aqt.mw.devicePixelRatioF()))
        except RuntimeError:
            dpr = 1.0
    pixel_size = QSize(max(1, round(size.width() * dpr)), max(1, round(size.height() * dpr)))
    pixmap = QPixmap(pixel_size)
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    night_mode = theme_manager.night_mode
    card_bg = QColor("#2A3038") if night_mode else QColor("#F3F6FA")
    card_border = QColor("#444B55") if night_mode else QColor("#C5CDD8")
    painter.setPen(QPen(card_border, 1))
    painter.setBrush(card_bg)
    rect_x = 3
    rect_y = 3
    rect_w = max(1, size.width() - 6)
    rect_h = max(1, size.height() - 6)
    painter.drawRoundedRect(rect_x, rect_y, rect_w, rect_h, 8, 8)

    flag_color = _flag_color(4)
    if flag_color is not None:
        font = QFont()
        font.setPixelSize(max(18, int(rect_h * 0.62)))
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(_FLAG_GLYPH)
        baseline_x = rect_x + (rect_w - text_width) // 2
        baseline_y = rect_y + (rect_h + metrics.ascent() - metrics.descent()) // 2
        path = QPainterPath()
        path.addText(baseline_x, baseline_y, font, _FLAG_GLYPH)

        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setBrush(_flag_theme_qcolor(flag_color, night_mode))
        painter.setPen(QPen(_outline_color_for_mode(mode, flag_color, night_mode), 1.2))
        painter.drawPath(path)

    painter.end()
    return QIcon(pixmap)


def _selection_style_tile_icon(
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

    row = outer.adjusted(6, 10, -6, -10)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(row_bg)
    painter.drawRoundedRect(row, 4, 4)

    if selection_style == _SELECTION_STYLE_CLASSIC:
        painter.setBrush(selected_blue)
        painter.drawRoundedRect(row, 4, 4)
    else:
        painter.setPen(QPen(border_blue, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(row.adjusted(0, 0, -1, -1), 4, 4)

    painter.end()
    return QIcon(pixmap)


class FlagOutlineConfigDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Flag Column Settings")
        self.resize(1140, 600)

        layout = QVBoxLayout(self)
        content = QHBoxLayout()
        content.setSpacing(18)
        options = QVBoxLayout()
        options.setSpacing(12)
        options.addWidget(QLabel("Flag outline color"))

        self._mode_buttons: dict[str, QToolButton] = {}
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        outline_tiles = QHBoxLayout()
        outline_tiles.setSpacing(8)
        for label, mode in (
            ("Auto", _OUTLINE_MODE_AUTO),
            ("Black", _OUTLINE_MODE_BLACK),
            ("White", _OUTLINE_MODE_WHITE),
            ("Match flag", _OUTLINE_MODE_FLAG),
        ):
            button = self._make_tile_button(
                label,
                _outline_mode_tile_icon(mode),
                icon_size=QSize(90, 56),
                minimum_size=QSize(106, 92),
            )
            self._mode_group.addButton(button)
            self._mode_buttons[mode] = button
            outline_tiles.addWidget(button)
        options.addLayout(outline_tiles)

        self._flag_border_checkbox = QCheckBox("Show flag border")
        options.addWidget(self._flag_border_checkbox)

        options.addSpacing(4)
        options.addWidget(QLabel("Selection style"))
        self._selection_buttons: dict[str, QToolButton] = {}
        self._selection_group = QButtonGroup(self)
        self._selection_group.setExclusive(True)
        selection_tiles = QHBoxLayout()
        selection_tiles.setSpacing(8)
        for label, style in (
            ("Classic fill", _SELECTION_STYLE_CLASSIC),
            ("Border only", _SELECTION_STYLE_BORDER),
        ):
            button = self._make_tile_button(
                label,
                _selection_style_tile_icon(style),
                icon_size=QSize(110, 42),
                minimum_size=QSize(0, 86),
                expand=True,
            )
            self._selection_group.addButton(button)
            self._selection_buttons[style] = button
            selection_tiles.addWidget(button, 1)
        options.addLayout(selection_tiles)

        self._state_icons_checkbox = QCheckBox("Show state icons")
        self._sticky_columns_checkbox = QCheckBox(
            "Keep Flag/State columns sticky while horizontally scrolling"
        )
        options.addSpacing(12)
        options.addWidget(self._state_icons_checkbox)
        options.addWidget(self._sticky_columns_checkbox)
        options.addStretch(1)
        content.addLayout(options, 1)

        preview_column = QVBoxLayout()
        preview_title = QLabel("Browser Preview")
        preview_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._browser_preview = _BrowserPreview(parent=self)
        preview_column.addWidget(preview_title)
        preview_column.addWidget(self._browser_preview, 1)
        content.addLayout(preview_column, 2)
        layout.addLayout(content)

        current = _OUTLINE_MODE if _OUTLINE_MODE in _OUTLINE_MODES else _OUTLINE_MODE_AUTO
        self._mode_buttons[current].setChecked(True)
        self._flag_border_checkbox.setChecked(_FLAG_BORDER_ENABLED)
        selected_style = (
            _SELECTION_STYLE if _SELECTION_STYLE in _SELECTION_STYLES else _SELECTION_STYLE_BORDER
        )
        self._selection_buttons[selected_style].setChecked(True)
        self._state_icons_checkbox.setChecked(_STATE_ICONS_ENABLED)
        self._sticky_columns_checkbox.setChecked(_STICKY_COLUMNS_ENABLED)
        self._sync_preview_mode()
        for button in self._mode_buttons.values():
            button.toggled.connect(self._sync_preview_mode)
        for button in self._selection_buttons.values():
            button.toggled.connect(self._sync_preview_mode)
        self._flag_border_checkbox.toggled.connect(self._sync_preview_mode)
        self._state_icons_checkbox.toggled.connect(self._sync_preview_mode)
        self._sticky_columns_checkbox.toggled.connect(self._sync_preview_mode)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _make_tile_button(
        text: str,
        icon: QIcon,
        *,
        icon_size: QSize,
        minimum_size: QSize,
        expand: bool = False,
    ) -> QToolButton:
        button = QToolButton()
        button.setCheckable(True)
        button.setAutoRaise(False)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setIcon(icon)
        button.setIconSize(icon_size)
        button.setText(text)
        button.setMinimumSize(minimum_size)
        if expand:
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return button

    def _sync_preview_mode(self, *_args) -> None:
        self._browser_preview.set_preview_options(
            self._selected_mode(),
            self._flag_border_checkbox.isChecked(),
            self._selected_selection_style(),
            self._state_icons_checkbox.isChecked(),
            self._sticky_columns_checkbox.isChecked(),
        )

    def _selected_mode(self) -> str:
        for mode, button in self._mode_buttons.items():
            if button.isChecked():
                return mode
        return _OUTLINE_MODE_AUTO

    def _selected_selection_style(self) -> str:
        for selection_style, button in self._selection_buttons.items():
            if button.isChecked():
                return selection_style
        return _SELECTION_STYLE_BORDER

    def accept(self) -> None:
        _save_settings(
            self._selected_mode(),
            flag_border_enabled=self._flag_border_checkbox.isChecked(),
            selection_style=self._selected_selection_style(),
            state_icons_enabled=self._state_icons_checkbox.isChecked(),
            sticky_columns_enabled=self._sticky_columns_checkbox.isChecked(),
        )
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
    _STATE_MARKED: adjusted_bg_color(colors.STATE_MARKED),
    _STATE_SUSPENDED: adjusted_bg_color(colors.STATE_SUSPENDED),
    _STATE_BURIED: adjusted_bg_color(colors.STATE_BURIED),
}

_STATE_ICON_COLORS = {
    _STATE_MARKED: colors.STATE_MARKED,
    _STATE_SUSPENDED: colors.STATE_SUSPENDED,
    _STATE_BURIED: colors.STATE_BURIED,
}


def _row_base_color(card) -> dict[str, str] | None:
    try:
        note = card.note()
    except NotFoundError:
        return None
    if note.has_tag("marked"):
        return _STATE_BG_COLORS[_STATE_MARKED]
    if card.queue == QUEUE_TYPE_SUSPENDED:
        return _STATE_BG_COLORS[_STATE_SUSPENDED]
    if card.queue in (QUEUE_TYPE_MANUALLY_BURIED, QUEUE_TYPE_SIBLING_BURIED):
        return _STATE_BG_COLORS[_STATE_BURIED]
    return None


def _state_keys_for_card(card) -> tuple[str, ...]:
    states: list[str] = []
    try:
        note = card.note()
    except NotFoundError:
        note = None
    if note is not None and note.has_tag("marked"):
        states.append(_STATE_MARKED)
    if card.queue == QUEUE_TYPE_SUSPENDED:
        states.append(_STATE_SUSPENDED)
    if card.queue in (QUEUE_TYPE_MANUALLY_BURIED, QUEUE_TYPE_SIBLING_BURIED):
        states.append(_STATE_BURIED)
    return tuple(state for state in _STATE_ORDER if state in states)


def _state_icon_fill(state: str) -> QColor:
    color = _STATE_ICON_COLORS.get(state)
    return theme_manager.qcolor(color) if color is not None else QColor("#9099A5")


def _badge_text_color(fill: QColor) -> QColor:
    luminance = 0.2126 * fill.red() + 0.7152 * fill.green() + 0.0722 * fill.blue()
    return QColor("#111111") if luminance > 150 else QColor("#F7F9FB")


def _state_background_for_keys(states: tuple[str, ...]) -> dict[str, str] | None:
    for state in _STATE_ORDER:
        if state in states:
            return _STATE_BG_COLORS.get(state)
    return None


def _flag_color(flag_index: int):
    return _FLAG_COLOR_BY_INDEX.get(flag_index)


class FlagIconDelegate(StatusDelegate):
    @staticmethod
    def _left_edge_column(view) -> int:
        column = view.columnAt(0)
        if column != -1:
            return column
        header = view.horizontalHeader()
        if header is None:
            return -1
        for visual in range(header.count()):
            logical = header.logicalIndex(visual)
            if logical != -1 and not view.isColumnHidden(logical):
                return logical
        return -1

    @staticmethod
    def _right_edge_column(view) -> int:
        viewport = view.viewport()
        if viewport is not None:
            column = view.columnAt(max(0, viewport.width() - 1))
            if column != -1:
                return column
        header = view.horizontalHeader()
        if header is None:
            return -1
        for visual in range(header.count() - 1, -1, -1):
            logical = header.logicalIndex(visual)
            if logical != -1 and not view.isColumnHidden(logical):
                return logical
        return -1

    def paint(
        self, painter: QPainter | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        view = option.widget
        selection = view.selectionModel() if view is not None else None
        is_selected = (
            selection.isRowSelected(index.row(), QModelIndex())
            if selection is not None
            else bool(option.state & QStyle.StateFlag.State_Selected)
        )
        paint_option = QStyleOptionViewItem(option)
        if is_selected and _SELECTION_STYLE == _SELECTION_STYLE_BORDER:
            # Keep browser state colors (suspended/buried/marked) visible on selection.
            paint_option.state &= ~QStyle.StateFlag.State_Selected
        super().paint(painter, paint_option, index)

        column_key = self._model.column_at(index).key
        if column_key not in (_FLAG_COLUMN_KEY, _STATE_COLUMN_KEY):
            self._paint_selection_border(painter, option, index, is_selected)
            return

        row = self._model.get_row(index)

        if column_key == _STATE_COLUMN_KEY:
            if painter is not None and _STATE_ICONS_ENABLED:
                self._paint_state_badges(
                    painter,
                    option.rect,
                    getattr(row, "_state_icons", ()),
                )
            self._paint_selection_border(painter, option, index, is_selected)
            return

        flag_index = getattr(row, "_flag_indicator", 0)
        if not flag_index or painter is None:
            self._paint_selection_border(painter, option, index, is_selected)
            return
        flag_color = _flag_color(flag_index)
        if flag_color is None:
            self._paint_selection_border(painter, option, index, is_selected)
            return
        rect = option.rect
        size = min(16, rect.height() - 2)
        if size <= 0:
            self._paint_selection_border(painter, option, index, is_selected)
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
        if _FLAG_BORDER_ENABLED:
            outline = _outline_color(flag_color)
            painter.setPen(QPen(outline, 1))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme_manager.qcolor(flag_color))
        painter.drawPath(path)
        painter.restore()
        self._paint_selection_border(painter, option, index, is_selected)

    def _paint_state_badges(self, painter: QPainter, rect, states: tuple[str, ...]) -> None:
        if not states:
            return
        count = len(states)
        spacing = 2
        badge_size = max(10, min(14, rect.height() - 6))
        total_width = (badge_size * count) + (spacing * (count - 1))
        start_x = rect.left() + max(1, (rect.width() - total_width) // 2)
        badge_y = rect.top() + max(1, (rect.height() - badge_size) // 2)

        base_font = QFont(painter.font())
        base_font.setBold(True)
        base_font.setPixelSize(max(8, badge_size - 5))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for idx, state in enumerate(states):
            badge_x = start_x + idx * (badge_size + spacing)
            fill = _state_icon_fill(state)
            text_color = _badge_text_color(fill)
            text = _STATE_BADGE_TEXT.get(state, "?")
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(badge_x, badge_y, badge_size, badge_size, 2.5, 2.5)
            painter.setPen(QPen(text_color, 1))
            symbol_font = QFont(base_font)
            if state == _STATE_MARKED:
                symbol_font.setPixelSize(max(10, badge_size - 1))
            elif state == _STATE_BURIED:
                symbol_font.setPixelSize(max(9, badge_size - 3))
            painter.setFont(symbol_font)
            painter.drawText(
                badge_x,
                badge_y,
                badge_size,
                badge_size,
                Qt.AlignmentFlag.AlignCenter,
                text,
            )
        painter.restore()

    def _paint_selection_border(
        self,
        painter: QPainter | None,
        option: QStyleOptionViewItem,
        index: QModelIndex,
        is_selected: bool,
    ) -> None:
        if _SELECTION_STYLE != _SELECTION_STYLE_BORDER or not is_selected or painter is None:
            return

        view = option.widget
        if view is None:
            return

        border = QColor("#20A7F7") if not theme_manager.night_mode else QColor("#67C8FF")
        rect = option.rect
        thickness = 3
        viewport = view.viewport()
        if viewport is None:
            return
        selection = view.selectionModel()
        model = view.model()
        if selection is None or model is None:
            return
        left_edge_column = self._left_edge_column(view)
        right_edge_column = self._right_edge_column(view)
        row = index.row()
        row_count = model.rowCount()
        prev_selected = (
            row > 0 and selection.isRowSelected(row - 1, QModelIndex())
        )
        next_selected = (
            row + 1 < row_count and selection.isRowSelected(row + 1, QModelIndex())
        )
        viewport_width = viewport.width()
        row_top = rect.top()
        row_bottom = rect.bottom() + 1
        is_overlay = getattr(view, "objectName", lambda: "")() == "flagStickyColumnsOverlay"
        sticky_active = False
        if not is_overlay and _STICKY_COLUMNS_ENABLED:
            bar = view.horizontalScrollBar()
            sticky_active = bar is not None and bar.value() > 0

        painter.save()
        if index.column() == left_edge_column:
            if not sticky_active:
                painter.fillRect(0, row_top, thickness, row_bottom - row_top, border)
            elif is_overlay:
                painter.fillRect(0, row_top, thickness, row_bottom - row_top, border)
        if index.column() == right_edge_column:
            if not prev_selected:
                painter.fillRect(0, row_top, viewport_width, thickness, border)
            if not next_selected:
                painter.fillRect(0, row_bottom - thickness, viewport_width, thickness, border)
        if index.column() == right_edge_column and not is_overlay:
            painter.fillRect(
                viewport_width - thickness,
                row_top,
                thickness,
                row_bottom - row_top,
                border,
            )
        painter.restore()


class _StickyColumnsOverlay(QObject):
    def __init__(self, view: QTableView) -> None:
        super().__init__(view)
        self._view = view
        self._enabled = False
        self._columns: tuple[int, ...] = ()

        overlay = QTableView(view)
        overlay.setObjectName("flagStickyColumnsOverlay")
        overlay.setFrameShape(QFrame.Shape.NoFrame)
        overlay.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        overlay.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        overlay.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        overlay.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        overlay.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        overlay.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        overlay.setSelectionMode(view.selectionMode())
        overlay.setWordWrap(False)
        overlay.setShowGrid(view.showGrid())
        overlay.setGridStyle(view.gridStyle())
        overlay.setAlternatingRowColors(view.alternatingRowColors())
        overlay.setFont(view.font())
        overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        vertical_header = overlay.verticalHeader()
        if vertical_header is not None:
            vertical_header.hide()
        horizontal_header = overlay.horizontalHeader()
        if horizontal_header is not None:
            horizontal_header.setHighlightSections(False)
            horizontal_header.setSectionsClickable(False)
            horizontal_header.setSectionsMovable(False)
            horizontal_header.setFont(view.horizontalHeader().font())

        overlay.hide()
        self._overlay = overlay
        self._sync_model_and_delegate()

        view.viewport().installEventFilter(self)
        view.installEventFilter(self)

        main_vertical_bar = view.verticalScrollBar()
        if main_vertical_bar is not None:
            main_vertical_bar.valueChanged.connect(self._sync_vertical_scroll)
        main_horizontal_bar = view.horizontalScrollBar()
        if main_horizontal_bar is not None:
            main_horizontal_bar.valueChanged.connect(self._on_horizontal_scroll)

        main_header = view.horizontalHeader()
        if main_header is not None:
            main_header.sectionResized.connect(self._on_column_resized)
            main_header.sectionMoved.connect(self._on_column_moved)

        main_vertical_header = view.verticalHeader()
        if main_vertical_header is not None:
            main_vertical_header.sectionResized.connect(self._on_row_resized)

    @property
    def view(self) -> QTableView:
        return self._view

    def _safe_view(self) -> QTableView | None:
        try:
            _ = self._view.viewport()
        except RuntimeError:
            return None
        return self._view

    def _safe_overlay(self) -> QTableView | None:
        try:
            _ = self._overlay.model()
        except RuntimeError:
            return None
        return self._overlay

    def _sync_model_and_delegate(self) -> None:
        view = self._safe_view()
        overlay = self._safe_overlay()
        if view is None or overlay is None:
            return
        model = view.model()
        selection_model = view.selectionModel()
        if model is not None:
            overlay.setModel(model)
        if selection_model is not None:
            overlay.setSelectionModel(selection_model)
        delegate = view.itemDelegate()
        if delegate is not None:
            overlay.setItemDelegate(delegate)
        overlay.setShowGrid(view.showGrid())
        overlay.setGridStyle(view.gridStyle())
        overlay.setAlternatingRowColors(view.alternatingRowColors())
        overlay.setFont(view.font())
        border = view.palette().color(QPalette.ColorRole.Mid).name()
        base = view.palette().color(QPalette.ColorRole.Base).name()
        overlay.setStyleSheet(
            f"QTableView#flagStickyColumnsOverlay {{"
            f"border-top: 1px solid {border};"
            f"border-left: 1px solid {border};"
            f"border-bottom: 1px solid {border};"
            f"border-right: 0px;"
            f"background: {base};"
            f"}}"
        )
        view_vertical_header = view.verticalHeader()
        overlay_vertical_header = overlay.verticalHeader()
        if view_vertical_header is not None and overlay_vertical_header is not None:
            overlay_vertical_header.setDefaultSectionSize(
                view_vertical_header.defaultSectionSize()
            )
        view_horizontal_header = view.horizontalHeader()
        overlay_horizontal_header = overlay.horizontalHeader()
        if view_horizontal_header is not None and overlay_horizontal_header is not None:
            overlay_horizontal_header.setDefaultSectionSize(
                view_horizontal_header.defaultSectionSize()
            )
            overlay_horizontal_header.setMinimumSectionSize(
                view_horizontal_header.minimumSectionSize()
            )
            overlay_horizontal_header.setFixedHeight(view_horizontal_header.height())
            overlay_horizontal_header.setFont(view_horizontal_header.font())

    def sync_delegate(self) -> None:
        view = self._safe_view()
        overlay = self._safe_overlay()
        if view is None or overlay is None:
            return
        delegate = view.itemDelegate()
        if delegate is not None:
            overlay.setItemDelegate(delegate)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self._update_overlay()

    def set_columns(self, columns: list[int]) -> None:
        self._columns = tuple(columns)
        self._sync_columns()
        self._update_overlay()

    def _sync_columns(self) -> None:
        view = self._safe_view()
        overlay = self._safe_overlay()
        if view is None or overlay is None:
            return
        model = overlay.model()
        if model is None:
            return
        sticky = set(self._columns)
        for column in range(model.columnCount()):
            overlay.setColumnHidden(column, column not in sticky)
        for column in self._columns:
            overlay.setColumnWidth(column, view.columnWidth(column))

    def _sticky_width(self) -> int:
        view = self._safe_view()
        if view is None:
            return 0
        width = 0
        for column in self._columns:
            if not view.isColumnHidden(column):
                width += view.columnWidth(column)
        return max(0, width)

    def _sync_visible_row_heights(self) -> None:
        view = self._safe_view()
        overlay = self._safe_overlay()
        if view is None or overlay is None:
            return
        model = view.model()
        viewport = view.viewport()
        if model is None or viewport is None:
            return
        top = view.rowAt(0)
        if top < 0:
            top = 0
        bottom = view.rowAt(max(0, viewport.height() - 1))
        if bottom < 0:
            bottom = min(model.rowCount() - 1, top)
        for row in range(top, bottom + 1):
            height = view.rowHeight(row)
            if overlay.rowHeight(row) != height:
                overlay.setRowHeight(row, height)

    def _update_overlay(self) -> None:
        overlay = self._safe_overlay()
        if overlay is None:
            return
        self._sync_model_and_delegate()
        self._sync_columns()
        if not self._enabled or not self._columns:
            overlay.hide()
            return

        view = self._safe_view()
        if view is None:
            overlay.hide()
            return
        width = self._sticky_width()
        if width <= 0:
            overlay.hide()
            return
        overlay.setGeometry(0, 0, width, view.height())
        self._sync_visible_row_heights()
        self._sync_vertical_scroll()
        overlay.show()
        overlay.raise_()
        view.viewport().update()

    def _sync_vertical_scroll(self, value: int | None = None) -> None:
        view = self._safe_view()
        overlay = self._safe_overlay()
        if view is None or overlay is None:
            return
        bar = view.verticalScrollBar()
        if bar is None:
            return
        if value is None:
            value = bar.value()
        overlay_bar = overlay.verticalScrollBar()
        if overlay_bar is not None and overlay_bar.value() != value:
            overlay_bar.setValue(value)

    def _on_column_resized(self, logical_index: int, _old_size: int, new_size: int) -> None:
        overlay = self._safe_overlay()
        if overlay is None:
            return
        if logical_index in self._columns:
            overlay.setColumnWidth(logical_index, new_size)
            self._update_overlay()

    def _on_column_moved(self, *_args) -> None:
        self._update_overlay()

    def _on_row_resized(self, row: int, _old_size: int, new_size: int) -> None:
        overlay = self._safe_overlay()
        if overlay is None:
            return
        overlay.setRowHeight(row, new_size)

    def _on_horizontal_scroll(self, _value: int) -> None:
        self._update_overlay()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        try:
            view = self._view
            viewport = view.viewport()
        except RuntimeError:
            return False
        if watched in (view, viewport) and event.type() == QEvent.Type.Resize:
            self._update_overlay()
        return super().eventFilter(watched, event)


_PREVIEW_ROLE_FLAG = int(Qt.ItemDataRole.UserRole) + 17
_PREVIEW_ROLE_STATES = int(Qt.ItemDataRole.UserRole) + 18
_PREVIEW_FLAG_COLUMN = 0
_PREVIEW_STATE_COLUMN = 1


class _BrowserPreviewDelegate(QStyledItemDelegate):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._outline_mode = _OUTLINE_MODE_AUTO
        self._flag_border_enabled = True
        self._selection_style = _SELECTION_STYLE_BORDER
        self._state_icons_enabled = True

    def set_preview_options(
        self,
        outline_mode: str,
        flag_border_enabled: bool,
        selection_style: str,
        state_icons_enabled: bool,
    ) -> None:
        self._outline_mode = (
            outline_mode if outline_mode in _OUTLINE_MODES else _OUTLINE_MODE_AUTO
        )
        self._flag_border_enabled = bool(flag_border_enabled)
        self._selection_style = (
            selection_style
            if selection_style in _SELECTION_STYLES
            else _SELECTION_STYLE_BORDER
        )
        self._state_icons_enabled = bool(state_icons_enabled)

    @staticmethod
    def _left_visible_column(view: QTableView) -> int:
        column = view.columnAt(0)
        if column != -1:
            return column
        header = view.horizontalHeader()
        if header is None:
            return -1
        for visual in range(header.count()):
            logical = header.logicalIndex(visual)
            if logical != -1 and not view.isColumnHidden(logical):
                return logical
        return -1

    @staticmethod
    def _right_visible_column(view: QTableView) -> int:
        viewport = view.viewport()
        if viewport is not None:
            column = view.columnAt(max(0, viewport.width() - 1))
            if column != -1:
                return column
        header = view.horizontalHeader()
        if header is None:
            return -1
        for visual in range(header.count() - 1, -1, -1):
            logical = header.logicalIndex(visual)
            if logical != -1 and not view.isColumnHidden(logical):
                return logical
        return -1

    def paint(
        self, painter: QPainter | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        if painter is None:
            return
        view = option.widget
        selection = view.selectionModel() if view is not None else None
        is_selected = (
            selection.isRowSelected(index.row(), QModelIndex())
            if selection is not None
            else bool(option.state & QStyle.StateFlag.State_Selected)
        )
        paint_option = QStyleOptionViewItem(option)
        if is_selected and self._selection_style == _SELECTION_STYLE_BORDER:
            paint_option.state &= ~QStyle.StateFlag.State_Selected
        super().paint(painter, paint_option, index)

        if view is None:
            return
        if index.column() == _PREVIEW_FLAG_COLUMN:
            self._paint_flag(painter, option.rect, index.data(_PREVIEW_ROLE_FLAG))
        elif index.column() == _PREVIEW_STATE_COLUMN and self._state_icons_enabled:
            states = index.data(_PREVIEW_ROLE_STATES)
            states_tuple = states if isinstance(states, tuple) else ()
            self._paint_state_badges(painter, option.rect, states_tuple)
        self._paint_selection_border(painter, option, index, is_selected)

    def _paint_flag(self, painter: QPainter, rect, flag_index) -> None:
        if not isinstance(flag_index, int) or flag_index <= 0:
            return
        flag_color = _flag_color(flag_index)
        if flag_color is None:
            return
        size = min(16, rect.height() - 2)
        if size <= 0:
            return
        font = QFont(painter.font())
        font.setPixelSize(size)
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(_FLAG_GLYPH)
        x = rect.left() + (rect.width() - text_width) // 2
        y = rect.top() + (rect.height() + metrics.ascent() - metrics.descent()) // 2
        path = QPainterPath()
        path.addText(x, y, font, _FLAG_GLYPH)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._flag_border_enabled:
            outline = _outline_color_for_mode(
                self._outline_mode, flag_color, theme_manager.night_mode
            )
            painter.setPen(QPen(outline, 1))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme_manager.qcolor(flag_color))
        painter.drawPath(path)
        painter.restore()

    def _paint_state_badges(self, painter: QPainter, rect, states: tuple[str, ...]) -> None:
        if not states:
            return
        count = len(states)
        spacing = 2
        badge_size = max(10, min(14, rect.height() - 6))
        total_width = (badge_size * count) + (spacing * (count - 1))
        start_x = rect.left() + max(1, (rect.width() - total_width) // 2)
        badge_y = rect.top() + max(1, (rect.height() - badge_size) // 2)

        base_font = QFont(painter.font())
        base_font.setBold(True)
        base_font.setPixelSize(max(8, badge_size - 5))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for idx, state in enumerate(states):
            badge_x = start_x + idx * (badge_size + spacing)
            fill = _state_icon_fill(state)
            text_color = _badge_text_color(fill)
            text = _STATE_BADGE_TEXT.get(state, "?")
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(badge_x, badge_y, badge_size, badge_size, 2.5, 2.5)
            painter.setPen(QPen(text_color, 1))
            symbol_font = QFont(base_font)
            if state == _STATE_MARKED:
                symbol_font.setPixelSize(max(11, badge_size + 1))
            elif state == _STATE_BURIED:
                symbol_font.setPixelSize(max(9, badge_size - 2))
            painter.setFont(symbol_font)
            painter.drawText(
                badge_x,
                badge_y,
                badge_size,
                badge_size,
                Qt.AlignmentFlag.AlignCenter,
                text,
            )
        painter.restore()

    def _paint_selection_border(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
        is_selected: bool,
    ) -> None:
        if self._selection_style != _SELECTION_STYLE_BORDER or not is_selected:
            return
        view = option.widget
        if view is None:
            return
        viewport = view.viewport()
        selection = view.selectionModel()
        model = view.model()
        if viewport is None or selection is None or model is None:
            return

        left_edge_column = self._left_visible_column(view)
        right_edge_column = self._right_visible_column(view)
        if left_edge_column < 0 or right_edge_column < 0:
            return

        border = QColor("#67C8FF") if theme_manager.night_mode else QColor("#20A7F7")
        thickness = 3
        row = index.row()
        row_count = model.rowCount()
        prev_selected = row > 0 and selection.isRowSelected(row - 1, QModelIndex())
        next_selected = row + 1 < row_count and selection.isRowSelected(row + 1, QModelIndex())
        row_top = option.rect.top()
        row_bottom = option.rect.bottom() + 1
        viewport_width = viewport.width()

        painter.save()
        if index.column() == left_edge_column:
            painter.fillRect(0, row_top, thickness, row_bottom - row_top, border)
        if index.column() == right_edge_column:
            if not prev_selected:
                painter.fillRect(0, row_top, viewport_width, thickness, border)
            if not next_selected:
                painter.fillRect(0, row_bottom - thickness, viewport_width, thickness, border)
            painter.fillRect(
                viewport_width - thickness, row_top, thickness, row_bottom - row_top, border
            )
        painter.restore()


class _BrowserPreview(QWidget):
    _HEADERS = (_FLAG_GLYPH, "State", "Sort Field", "Deck", "Created", "Reviews", "Due")
    _COLUMN_WIDTHS = (34, 88, 390, 230, 118, 84, 162)
    _ROWS = (
        (
            0,
            (),
            "{c1::Conduction velocity} is the speed of signal propagation",
            "Medical School",
            "2016-08-11",
            "0",
            "(New #3184)",
        ),
        (
            2,
            (_STATE_SUSPENDED,),
            "Which part of the neuron receives input first?",
            "Medical School",
            "2016-11-17",
            "0",
            "(New #3730)",
        ),
        (
            5,
            (_STATE_MARKED,),
            "{c2::Astrocytes} are glial cells that support injured neurons",
            "Medical School",
            "2016-11-17",
            "0",
            "(New #3732)",
        ),
        (
            2,
            (_STATE_BURIED,),
            "In myelinated cells, nodes of Ranvier allow saltatory conduction",
            "Medical School",
            "2016-11-17",
            "0",
            "(New #3733)",
        ),
        (
            0,
            (_STATE_MARKED, _STATE_SUSPENDED),
            "Guillain-Barre syndrome typically causes ascending weakness",
            "Medical School",
            "2017-01-29",
            "0",
            "(New #4122)",
        ),
        (
            1,
            (),
            "Multiple sclerosis lesions are best seen on MRI FLAIR sequences",
            "Neurology",
            "2017-02-14",
            "2",
            "(New #4310)",
        ),
        (
            0,
            (),
            "{c1::Microglia} are activated during CNS inflammation",
            "Neuro Path",
            "2017-03-04",
            "0",
            "(New #4450)",
        ),
        (
            3,
            (_STATE_BURIED,),
            "Amyotrophic lateral sclerosis affects upper and lower motor neurons",
            "Medical School",
            "2017-03-19",
            "0",
            "(New #4506)",
        ),
        (
            0,
            (),
            "One feature of Parkinson disease is resting tremor and bradykinesia",
            "Neurology",
            "2017-04-02",
            "1",
            "(New #4582)",
        ),
        (
            7,
            (_STATE_MARKED,),
            "A lateral medullary stroke can cause dysphagia and hoarseness",
            "Neuroanatomy",
            "2017-04-18",
            "0",
            "(New #4630)",
        ),
        (
            0,
            (),
            "Which cranial nerve carries taste from the anterior tongue?",
            "Medical School",
            "2017-05-01",
            "0",
            "(New #4709)",
        ),
        (
            4,
            (_STATE_SUSPENDED,),
            "Spinal cord hemisection causes ipsilateral vibration loss",
            "Neuroscience",
            "2017-05-20",
            "3",
            "(New #4825)",
        ),
        (
            0,
            (),
            "Neurofibromatosis type 1 is associated with cafe-au-lait spots",
            "Neurocutaneous",
            "2017-06-02",
            "0",
            "(New #4890)",
        ),
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._state_icons_enabled = True
        self._sticky_columns_enabled = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._table = QTableView(self)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._table.setWordWrap(False)
        self._table.setShowGrid(True)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().hide()
        self._table.verticalHeader().setDefaultSectionSize(32)
        horizontal_header = self._table.horizontalHeader()
        horizontal_header.setStretchLastSection(False)
        horizontal_header.setHighlightSections(False)
        horizontal_header.setSectionsClickable(False)

        self._model = QStandardItemModel(self)
        self._table.setModel(self._model)
        self._delegate = _BrowserPreviewDelegate(self._table)
        self._table.setItemDelegate(self._delegate)
        self._sticky_overlay = _StickyColumnsOverlay(self._table)
        self._sticky_overlay.set_enabled(False)
        self._apply_selection_palette()
        self._build_preview_rows()
        self._table.selectRow(1)
        self._ensure_example_multi_selection()
        layout.addWidget(self._table)
        self.setMinimumSize(660, 430)

    def _apply_selection_palette(self) -> None:
        palette = self._table.palette()
        if theme_manager.night_mode:
            highlight = QColor("#3F8FFF")
            text = QColor("#F8FAFF")
        else:
            highlight = QColor("#8CC9FF")
            text = QColor("#11233A")
        palette.setColor(QPalette.ColorRole.Highlight, highlight)
        palette.setColor(QPalette.ColorRole.HighlightedText, text)
        self._table.setPalette(palette)

    def _build_preview_rows(self) -> None:
        self._model.clear()
        self._model.setColumnCount(len(self._HEADERS))
        self._model.setHorizontalHeaderLabels(self._HEADERS)

        night_mode = theme_manager.night_mode
        neutral = QColor("#2A333D") if night_mode else QColor("#FFFFFF")
        neutral_alt = QColor("#2D3742") if night_mode else QColor("#F7FAFD")

        for row_index, row_data in enumerate(self._ROWS):
            flag_index, states, sort_field, deck, created, reviews, due = row_data
            state_bg = _state_background_for_keys(states)
            row_bg = (
                _flag_theme_qcolor(state_bg, night_mode)
                if state_bg is not None
                else (neutral if row_index % 2 == 0 else neutral_alt)
            )
            values = ("", "", sort_field, deck, created, reviews, due)
            items: list[QStandardItem] = []
            for column, value in enumerate(values):
                item = QStandardItem(value)
                item.setEditable(False)
                item.setData(flag_index, _PREVIEW_ROLE_FLAG)
                item.setData(states, _PREVIEW_ROLE_STATES)
                item.setData(row_bg, Qt.ItemDataRole.BackgroundRole)
                if column in (_PREVIEW_FLAG_COLUMN, _PREVIEW_STATE_COLUMN, 5):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                else:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    )
                items.append(item)
            self._model.appendRow(items)

        header = self._table.horizontalHeader()
        for column, width in enumerate(self._COLUMN_WIDTHS):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self._table.setColumnWidth(column, width)

    def _ensure_example_multi_selection(self) -> None:
        selection_model = self._table.selectionModel()
        if selection_model is None or self._model.rowCount() < 3:
            return
        for row in (1, 2):
            index = self._model.index(row, 0)
            selection_model.select(
                index,
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows,
            )
        self._table.setCurrentIndex(self._model.index(1, 2))

    def _ensure_has_selection(self) -> None:
        selection_model = self._table.selectionModel()
        if selection_model is None or selection_model.hasSelection():
            return
        row = 1 if self._model.rowCount() > 1 else 0
        if row >= 0:
            self._table.selectRow(row)

    def set_preview_options(
        self,
        outline_mode: str,
        flag_border_enabled: bool,
        selection_style: str,
        state_icons_enabled: bool,
        sticky_columns_enabled: bool,
    ) -> None:
        self._delegate.set_preview_options(
            outline_mode,
            flag_border_enabled,
            selection_style,
            state_icons_enabled,
        )
        self._state_icons_enabled = bool(state_icons_enabled)
        self._sticky_columns_enabled = bool(sticky_columns_enabled)
        self._table.setColumnHidden(_PREVIEW_STATE_COLUMN, not self._state_icons_enabled)
        sticky_columns = [_PREVIEW_FLAG_COLUMN]
        if self._state_icons_enabled:
            sticky_columns.append(_PREVIEW_STATE_COLUMN)
        self._sticky_overlay.set_columns(sticky_columns)
        self._sticky_overlay.sync_delegate()
        self._sticky_overlay.set_enabled(self._sticky_columns_enabled)
        self._ensure_has_selection()
        self._table.viewport().update()
        header = self._table.horizontalHeader()
        if header is not None:
            header.viewport().update()


def _on_browser_did_fetch_columns(columns: dict[str, Column]) -> None:
    if _FLAG_COLUMN_KEY not in columns:
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
    if _STATE_COLUMN_KEY in columns:
        return
    columns[_STATE_COLUMN_KEY] = Column(
        key=_STATE_COLUMN_KEY,
        cards_mode_label="State",
        notes_mode_label="State",
        sorting_cards=Columns.SORTING_NONE,
        sorting_notes=Columns.SORTING_NONE,
        uses_cell_font=False,
        alignment=Columns.ALIGNMENT_CENTER,
        cards_mode_tooltip="Card states: Marked (*), Suspended (!), Buried (→)",
        notes_mode_tooltip="Card states: Marked (*), Suspended (!), Buried (→)",
    )


def _on_browser_did_fetch_row(card_or_note_id, is_note, row, columns) -> None:
    row._flag_indicator = 0
    row._state_icons = ()
    if is_note:
        return
    row_is_flagged = _color_key(row.color) in _FLAG_BG_KEYS
    if not row_is_flagged and not _STATE_ICONS_ENABLED:
        return
    if aqt.mw is None or aqt.mw.col is None:
        return
    try:
        card = aqt.mw.col.get_card(card_or_note_id)
    except NotFoundError:
        return
    if row_is_flagged:
        row._flag_indicator = card.user_flag()
        row.color = _row_base_color(card)
    if _STATE_ICONS_ENABLED:
        row._state_icons = _state_keys_for_card(card)


def _set_column_visibility(model, key: str, visible: bool) -> None:
    active = model.active_column_index(key)
    if visible and active is None:
        model.toggle_column(key)
    elif not visible and active is not None:
        model.toggle_column(key)


def _configure_browser_table(browser) -> None:
    view = browser.table._view
    model = browser.table._model
    if view is None or model is None:
        return

    _set_column_visibility(model, _FLAG_COLUMN_KEY, True)
    _set_column_visibility(model, _STATE_COLUMN_KEY, _STATE_ICONS_ENABLED)

    header = view.horizontalHeader()
    if header is None:
        return

    min_width = min(_FLAG_COLUMN_WIDTH, _STATE_COLUMN_WIDTH)
    if header.minimumSectionSize() > min_width:
        header.setMinimumSectionSize(min_width)

    flag_column = model.active_column_index(_FLAG_COLUMN_KEY)
    state_column = model.active_column_index(_STATE_COLUMN_KEY)

    if flag_column is not None:
        visual = header.visualIndex(flag_column)
        if visual != 0:
            header.moveSection(visual, 0)
        header.setSectionResizeMode(flag_column, QHeaderView.ResizeMode.Fixed)
        view.setColumnWidth(flag_column, _FLAG_COLUMN_WIDTH)

    if state_column is not None:
        target_visual = 1 if flag_column is not None else 0
        visual = header.visualIndex(state_column)
        if visual != target_visual:
            header.moveSection(visual, target_visual)
        header.setSectionResizeMode(state_column, QHeaderView.ResizeMode.Fixed)
        view.setColumnWidth(state_column, _STATE_COLUMN_WIDTH)

    sticky_overlay = getattr(browser, "_flag_sticky_overlay", None)
    sticky_columns: list[int] = []
    if flag_column is not None:
        sticky_columns.append(flag_column)
    if state_column is not None:
        sticky_columns.append(state_column)

    if _STICKY_COLUMNS_ENABLED and sticky_columns:
        if sticky_overlay is None or sticky_overlay.view is not view:
            sticky_overlay = _StickyColumnsOverlay(view)
            browser._flag_sticky_overlay = sticky_overlay
        sticky_overlay.set_columns(sticky_columns)
        sticky_overlay.sync_delegate()
        sticky_overlay.set_enabled(True)
    elif sticky_overlay is not None:
        sticky_overlay.set_enabled(False)


def _on_browser_will_show(browser) -> None:
    view = browser.table._view
    if view is None:
        return
    model = browser.table._model
    if model is None:
        return
    delegate = getattr(browser, "_flag_icon_delegate", None)
    if delegate is None:
        delegate = FlagIconDelegate(browser, model)
        browser._flag_icon_delegate = delegate
    view.setItemDelegate(delegate)
    _configure_browser_table(browser)


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

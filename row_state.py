from __future__ import annotations

import aqt
from anki.consts import (
    QUEUE_TYPE_MANUALLY_BURIED,
    QUEUE_TYPE_SIBLING_BURIED,
    QUEUE_TYPE_SUSPENDED,
)
from anki.errors import NotFoundError
from aqt import colors
from aqt.browser.table import adjusted_bg_color
from aqt.qt import QColor, Qt
from aqt.theme import theme_manager

from .config import get_settings
from .constants import (
    FLAG_COLOR_BY_INDEX,
    OUTLINE_MODE_BLACK,
    OUTLINE_MODE_FLAG,
    OUTLINE_MODE_WHITE,
    STATE_BADGE_TEXT,
    STATE_BURIED,
    STATE_MARKED,
    STATE_ORDER,
    STATE_SUSPENDED,
)


def flag_color(flag_index: int) -> dict[str, str] | None:
    return FLAG_COLOR_BY_INDEX.get(flag_index)


def theme_qcolor(color: dict[str, str] | None, night_mode: bool | None = None) -> QColor:
    if color is None:
        return QColor()

    if night_mode is None:
        night_mode = theme_manager.night_mode

    key = "dark" if night_mode else "light"
    value = color.get(key) or color.get("light") or color.get("dark")
    return QColor(value) if value else QColor()


def outline_qcolor(
    mode: str, color: dict[str, str] | None, night_mode: bool | None = None
) -> QColor | Qt.GlobalColor:
    if night_mode is None:
        night_mode = theme_manager.night_mode

    if mode == OUTLINE_MODE_BLACK:
        return Qt.GlobalColor.black
    if mode == OUTLINE_MODE_WHITE:
        return Qt.GlobalColor.white
    if mode == OUTLINE_MODE_FLAG and color is not None:
        return theme_qcolor(color, night_mode)
    return Qt.GlobalColor.white if night_mode else Qt.GlobalColor.black


def selection_border_qcolor() -> QColor:
    return QColor("#67C8FF") if theme_manager.night_mode else QColor("#20A7F7")


def state_icon_fill(state: str) -> QColor:
    color = _STATE_ICON_COLORS.get(state)
    return theme_manager.qcolor(color) if color is not None else QColor("#9099A5")


def badge_text_color(fill: QColor) -> QColor:
    luminance = 0.2126 * fill.red() + 0.7152 * fill.green() + 0.0722 * fill.blue()
    return QColor("#111111") if luminance > 150 else QColor("#F7F9FB")


def state_background_for_keys(states: tuple[str, ...]) -> dict[str, str] | None:
    for state in STATE_ORDER:
        if state in states:
            return _STATE_BG_COLORS.get(state)
    return None


def state_badge_text(state: str) -> str:
    return STATE_BADGE_TEXT.get(state, "?")


def card_state_keys(card) -> tuple[str, ...]:
    states: list[str] = []
    try:
        note = card.note()
    except NotFoundError:
        note = None

    if note is not None and note.has_tag("marked"):
        states.append(STATE_MARKED)
    if card.queue == QUEUE_TYPE_SUSPENDED:
        states.append(STATE_SUSPENDED)
    if card.queue in (QUEUE_TYPE_MANUALLY_BURIED, QUEUE_TYPE_SIBLING_BURIED):
        states.append(STATE_BURIED)

    return tuple(state for state in STATE_ORDER if state in states)


def card_base_background(card) -> dict[str, str] | None:
    try:
        note = card.note()
    except NotFoundError:
        return None

    if note.has_tag("marked"):
        return _STATE_BG_COLORS[STATE_MARKED]
    if card.queue == QUEUE_TYPE_SUSPENDED:
        return _STATE_BG_COLORS[STATE_SUSPENDED]
    if card.queue in (QUEUE_TYPE_MANUALLY_BURIED, QUEUE_TYPE_SIBLING_BURIED):
        return _STATE_BG_COLORS[STATE_BURIED]
    return None


def populate_browser_row(item_id, is_note: bool, row) -> None:
    row._flag_indicator = 0
    row._state_icons = ()

    if is_note or aqt.mw is None or aqt.mw.col is None:
        return

    settings = get_settings()
    row_is_flagged = _color_key(row.color) in _FLAG_BG_KEYS
    if not row_is_flagged and not settings.state_icons_enabled:
        return

    try:
        card = aqt.mw.col.get_card(item_id)
    except NotFoundError:
        return

    if row_is_flagged:
        row._flag_indicator = card.user_flag()
        row.color = card_base_background(card)
    if settings.state_icons_enabled:
        row._state_icons = card_state_keys(card)


def _color_key(color: dict[str, str] | None) -> tuple[str | None, str | None] | None:
    if not color:
        return None
    return (color.get("light"), color.get("dark"))


_FLAG_BG_KEYS = {
    key
    for key in (
        _color_key(adjusted_bg_color(color))
        for color in FLAG_COLOR_BY_INDEX.values()
    )
    if key is not None
}

_STATE_BG_COLORS = {
    STATE_MARKED: adjusted_bg_color(colors.STATE_MARKED),
    STATE_SUSPENDED: adjusted_bg_color(colors.STATE_SUSPENDED),
    STATE_BURIED: adjusted_bg_color(colors.STATE_BURIED),
}

_STATE_ICON_COLORS = {
    STATE_MARKED: colors.STATE_MARKED,
    STATE_SUSPENDED: colors.STATE_SUSPENDED,
    STATE_BURIED: colors.STATE_BURIED,
}

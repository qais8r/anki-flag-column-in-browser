from __future__ import annotations

from aqt import colors
from aqt.qt import Qt

ADDON_NAME = "Flag Column in Browser"
ADDON_AUTHOR = "Qaisar"
ADDON_VERSION = "2.1"
ADDON_DESCRIPTION = "Shows a flag indicator column in the Anki Browser."

FLAG_GLYPH = "⚑"

FLAG_COLUMN_KEY = "_flag_indicator"
FLAG_COLUMN_WIDTH = 21

STATE_COLUMN_KEY = "_state_icons"
STATE_COLUMN_WIDTH = 44

OUTLINE_CONFIG_KEY = "flag_outline"
FLAG_BORDER_CONFIG_KEY = "flag_border_enabled"
SELECTION_STYLE_CONFIG_KEY = "selection_style"
SELECTION_BORDER_LEGACY_CONFIG_KEY = "selection_border_enabled"
STATE_ICONS_CONFIG_KEY = "state_icons_enabled"
STICKY_COLUMNS_CONFIG_KEY = "sticky_columns_enabled"

OUTLINE_MODE_AUTO = "auto"
OUTLINE_MODE_BLACK = "black"
OUTLINE_MODE_WHITE = "white"
OUTLINE_MODE_FLAG = "flag"
OUTLINE_MODES = {
    OUTLINE_MODE_AUTO,
    OUTLINE_MODE_BLACK,
    OUTLINE_MODE_WHITE,
    OUTLINE_MODE_FLAG,
}

SELECTION_STYLE_CLASSIC = "classic"
SELECTION_STYLE_BORDER = "border"
SELECTION_STYLES = {
    SELECTION_STYLE_CLASSIC,
    SELECTION_STYLE_BORDER,
}

STATE_MARKED = "marked"
STATE_SUSPENDED = "suspended"
STATE_BURIED = "buried"
STATE_ORDER = (STATE_MARKED, STATE_SUSPENDED, STATE_BURIED)
STATE_BADGE_TEXT = {
    STATE_MARKED: "✱",
    STATE_SUSPENDED: "!",
    STATE_BURIED: "→",
}

FLAG_COLOR_BY_INDEX = {
    1: colors.FLAG_1,
    2: colors.FLAG_2,
    3: colors.FLAG_3,
    4: colors.FLAG_4,
    5: colors.FLAG_5,
    6: colors.FLAG_6,
    7: colors.FLAG_7,
}

PREVIEW_ROLE_FLAG = int(Qt.ItemDataRole.UserRole) + 17
PREVIEW_ROLE_STATES = int(Qt.ItemDataRole.UserRole) + 18
PREVIEW_FLAG_COLUMN = 0
PREVIEW_STATE_COLUMN = 1

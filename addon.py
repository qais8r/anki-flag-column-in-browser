from __future__ import annotations

import aqt
from anki.collection import BrowserColumns as Columns
from aqt import gui_hooks
from aqt.browser.table import Column
from aqt.qt import QHeaderView, QObject

from .config import addon_module_name, get_settings, refresh_settings
from .constants import (
    FLAG_COLUMN_KEY,
    FLAG_COLUMN_WIDTH,
    FLAG_GLYPH,
    STATE_COLUMN_KEY,
    STATE_COLUMN_WIDTH,
)
from .painting import BrowserStatusDelegate
from .row_state import populate_browser_row
from .settings_dialog import FlagColumnSettingsDialog
from .view_support import FrozenColumnsController, SelectionBorderOverlay

_HOOKS_REGISTERED = False


class BrowserTableController(QObject):
    def __init__(self, browser) -> None:
        super().__init__(browser)
        self.browser = browser
        self._view = browser.table._view
        self._model = browser.table._model
        self._delegate = BrowserStatusDelegate(browser, self._model)
        self._selection_overlay = SelectionBorderOverlay(self._view)
        self._frozen_columns = FrozenColumnsController(
            self._view,
            self._selection_overlay,
        )

    @property
    def view(self):
        return self._view

    def refresh(self) -> None:
        settings = get_settings()
        self._view.setItemDelegate(self._delegate)
        self._ensure_column_visibility(FLAG_COLUMN_KEY, True)
        self._ensure_column_visibility(STATE_COLUMN_KEY, settings.state_icons_enabled)

        header = self._view.horizontalHeader()
        if header is None:
            return

        min_width = min(FLAG_COLUMN_WIDTH, STATE_COLUMN_WIDTH)
        if header.minimumSectionSize() > min_width:
            header.setMinimumSectionSize(min_width)

        flag_column = self._model.active_column_index(FLAG_COLUMN_KEY)
        state_column = self._model.active_column_index(STATE_COLUMN_KEY)

        if flag_column is not None:
            self._move_column_to_visual_index(flag_column, 0)
            header.setSectionResizeMode(flag_column, QHeaderView.ResizeMode.Fixed)
            self._view.setColumnWidth(flag_column, FLAG_COLUMN_WIDTH)

        if state_column is not None:
            target_visual = 1 if flag_column is not None else 0
            self._move_column_to_visual_index(state_column, target_visual)
            header.setSectionResizeMode(state_column, QHeaderView.ResizeMode.Fixed)
            self._view.setColumnWidth(state_column, STATE_COLUMN_WIDTH)

        sticky_columns: list[int] = []
        if flag_column is not None:
            sticky_columns.append(flag_column)
        if state_column is not None:
            sticky_columns.append(state_column)

        self._frozen_columns.set_columns(sticky_columns)
        self._frozen_columns.set_enabled(settings.sticky_columns_enabled)
        self._selection_overlay.refresh()
        self._view.viewport().update()
        header.viewport().update()

    def _ensure_column_visibility(self, key: str, visible: bool) -> None:
        active = self._model.active_column_index(key)
        if visible and active is None:
            self._model.toggle_column(key)
        elif not visible and active is not None:
            self._model.toggle_column(key)

    def _move_column_to_visual_index(self, logical_index: int, visual_index: int) -> None:
        header = self._view.horizontalHeader()
        if header is None:
            return
        current_visual = header.visualIndex(logical_index)
        if current_visual != visual_index and current_visual >= 0:
            header.moveSection(current_visual, visual_index)


def get_or_create_browser_controller(browser) -> BrowserTableController | None:
    view = browser.table._view
    model = browser.table._model
    if view is None or model is None:
        return None

    controller = getattr(browser, "_flag_column_controller", None)
    if controller is None or controller.view is not view:
        controller = BrowserTableController(browser)
        browser._flag_column_controller = controller
    return controller


def refresh_browser_view() -> None:
    if aqt.mw is None:
        return

    browser = getattr(aqt.mw, "browser", None)
    if browser is None:
        return

    controller = get_or_create_browser_controller(browser)
    if controller is None:
        return

    controller.refresh()
    redraw = getattr(browser.table, "redraw_cells", None)
    if callable(redraw):
        redraw()
    else:
        controller.view.viewport().update()


def open_settings_dialog() -> None:
    if aqt.mw is None:
        return

    dialog = FlagColumnSettingsDialog(aqt.mw)
    if dialog.exec():
        refresh_browser_view()


def setup_config_menu() -> None:
    if aqt.mw is None:
        return
    if getattr(aqt.mw, "_flag_column_settings_action", None) is not None:
        return

    action = aqt.mw.form.menuTools.addAction("Flag Column Settings...")
    action.triggered.connect(open_settings_dialog)
    aqt.mw._flag_column_settings_action = action


def on_browser_did_fetch_columns(columns: dict[str, Column]) -> None:
    if FLAG_COLUMN_KEY not in columns:
        columns[FLAG_COLUMN_KEY] = Column(
            key=FLAG_COLUMN_KEY,
            cards_mode_label=FLAG_GLYPH,
            notes_mode_label=FLAG_GLYPH,
            sorting_cards=Columns.SORTING_NONE,
            sorting_notes=Columns.SORTING_NONE,
            uses_cell_font=False,
            alignment=Columns.ALIGNMENT_CENTER,
            cards_mode_tooltip=f"{FLAG_GLYPH} Flagged cards",
            notes_mode_tooltip=f"{FLAG_GLYPH} Flagged notes",
        )

    if STATE_COLUMN_KEY not in columns:
        columns[STATE_COLUMN_KEY] = Column(
            key=STATE_COLUMN_KEY,
            cards_mode_label="State",
            notes_mode_label="State",
            sorting_cards=Columns.SORTING_NONE,
            sorting_notes=Columns.SORTING_NONE,
            uses_cell_font=False,
            alignment=Columns.ALIGNMENT_CENTER,
            cards_mode_tooltip="Card states: Marked (*), Suspended (!), Buried (→)",
            notes_mode_tooltip="Card states: Marked (*), Suspended (!), Buried (→)",
        )


def on_browser_did_fetch_row(item_id, is_note, row, _columns) -> None:
    populate_browser_row(item_id, is_note, row)


def on_browser_will_show(browser) -> None:
    controller = get_or_create_browser_controller(browser)
    if controller is not None:
        controller.refresh()


def on_config_updated(*_args, **_kwargs) -> None:
    refresh_settings()
    refresh_browser_view()


def on_profile_did_open() -> None:
    refresh_settings()
    setup_config_menu()
    if aqt.mw is not None:
        aqt.mw.addonManager.setConfigUpdatedAction(addon_module_name(), on_config_updated)


def register_hooks() -> None:
    global _HOOKS_REGISTERED
    if _HOOKS_REGISTERED:
        return

    gui_hooks.browser_did_fetch_columns.append(on_browser_did_fetch_columns)
    gui_hooks.browser_did_fetch_row.append(on_browser_did_fetch_row)
    gui_hooks.browser_will_show.append(on_browser_will_show)
    gui_hooks.profile_did_open.append(on_profile_did_open)
    _HOOKS_REGISTERED = True

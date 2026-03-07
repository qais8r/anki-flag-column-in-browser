from __future__ import annotations

from aqt.qt import (
    QAbstractItemView,
    QHeaderView,
    QPalette,
    QStandardItem,
    QStandardItemModel,
    QTableView,
    QVBoxLayout,
    QWidget,
    Qt,
    QColor,
)
from aqt.theme import theme_manager

from .config import AddonSettings
from .constants import (
    FLAG_GLYPH,
    PREVIEW_FLAG_COLUMN,
    PREVIEW_ROLE_FLAG,
    PREVIEW_ROLE_STATES,
    PREVIEW_STATE_COLUMN,
    SELECTION_STYLE_CLASSIC,
    STATE_BURIED,
    STATE_MARKED,
    STATE_SUSPENDED,
)
from .painting import PreviewDelegate
from .row_state import state_background_for_keys, theme_qcolor
from .view_support import FrozenColumnsController, SelectionBorderOverlay


class BrowserPreview(QWidget):
    _SELECTED_ROW = 4
    _HEADERS = (FLAG_GLYPH, "State", "Sort Field", "Deck", "Created", "Reviews", "Due")
    _COLUMN_WIDTHS = (34, 54, 390, 230, 118, 84, 162)
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
            (STATE_SUSPENDED,),
            "Which part of the neuron receives input first?",
            "Medical School",
            "2016-11-17",
            "0",
            "(New #3730)",
        ),
        (
            5,
            (STATE_MARKED,),
            "{c2::Astrocytes} are glial cells that support injured neurons",
            "Medical School",
            "2016-11-17",
            "0",
            "(New #3732)",
        ),
        (
            2,
            (STATE_BURIED,),
            "In myelinated cells, nodes of Ranvier allow saltatory conduction",
            "Medical School",
            "2016-11-17",
            "0",
            "(New #3733)",
        ),
        (
            0,
            (STATE_MARKED, STATE_SUSPENDED),
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
            (STATE_BURIED,),
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
            (STATE_MARKED,),
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
            (STATE_SUSPENDED,),
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
        self._settings = AddonSettings()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableView(self)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._table.setWordWrap(False)
        self._table.setShowGrid(True)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().hide()
        self._table.verticalHeader().setDefaultSectionSize(32)

        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setHighlightSections(False)
        header.setSectionsClickable(False)

        self._model = QStandardItemModel(self)
        self._table.setModel(self._model)

        self._delegate = PreviewDelegate(self._table)
        self._delegate.set_draw_selection_border(True)
        self._delegate.set_preview_selected_row(self._SELECTED_ROW)
        self._table.setItemDelegate(self._delegate)

        self._selection_overlay = SelectionBorderOverlay(
            self._table,
            selection_style_getter=self._overlay_selection_style,
        )
        self._frozen_columns = FrozenColumnsController(
            self._table,
            self._selection_overlay,
            selection_style_getter=self._overlay_selection_style,
        )
        self._apply_selection_palette()
        self._build_rows()

        layout.addWidget(self._table)
        self.setMinimumSize(660, 430)
        self.set_settings(self._settings)
        self._scroll_to_left()

    def set_settings(self, settings: AddonSettings) -> None:
        self._settings = settings
        self._delegate.set_settings(settings)
        self._table.setColumnHidden(PREVIEW_STATE_COLUMN, not settings.state_icons_enabled)

        sticky_columns = [PREVIEW_FLAG_COLUMN]
        if settings.state_icons_enabled:
            sticky_columns.append(PREVIEW_STATE_COLUMN)

        self._frozen_columns.set_columns(sticky_columns)
        self._frozen_columns.set_enabled(settings.sticky_columns_enabled)
        self._selection_overlay.refresh()
        self._frozen_columns.refresh()
        self._table.viewport().update()

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

    def _build_rows(self) -> None:
        self._model.clear()
        self._model.setColumnCount(len(self._HEADERS))
        self._model.setHorizontalHeaderLabels(self._HEADERS)

        night_mode = theme_manager.night_mode
        neutral = QColor("#2A333D") if night_mode else QColor("#FFFFFF")
        neutral_alt = QColor("#2D3742") if night_mode else QColor("#F7FAFD")

        for row_index, row_data in enumerate(self._ROWS):
            flag_index, states, sort_field, deck, created, reviews, due = row_data
            state_bg = state_background_for_keys(states)
            row_bg = (
                theme_qcolor(state_bg, night_mode)
                if state_bg is not None
                else (neutral if row_index % 2 == 0 else neutral_alt)
            )
            values = ("", "", sort_field, deck, created, reviews, due)
            items: list[QStandardItem] = []

            for column, value in enumerate(values):
                item = QStandardItem(value)
                item.setEditable(False)
                item.setData(flag_index, PREVIEW_ROLE_FLAG)
                item.setData(states, PREVIEW_ROLE_STATES)
                item.setData(row_bg, Qt.ItemDataRole.BackgroundRole)
                if column in (PREVIEW_FLAG_COLUMN, PREVIEW_STATE_COLUMN, 5):
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

    def _scroll_to_left(self) -> None:
        bar = self._table.horizontalScrollBar()
        if bar is None:
            return
        bar.setValue(bar.minimum())

    def _overlay_selection_style(self) -> str:
        return SELECTION_STYLE_CLASSIC

from __future__ import annotations

from typing import Callable, TypeVar

from aqt.qt import (
    QAbstractItemModel,
    QAbstractItemView,
    QEvent,
    QFrame,
    QHeaderView,
    QModelIndex,
    QObject,
    QPainter,
    QPalette,
    QSignalBlocker,
    QTableView,
    QWidget,
    Qt,
)

from .config import get_settings
from .constants import SELECTION_STYLE_BORDER
from .row_state import selection_border_qcolor


_T = TypeVar("_T")


def _safe_qobject(obj: _T | None) -> _T | None:
    if obj is None:
        return None
    try:
        obj.objectName()
    except RuntimeError:
        return None
    return obj


class SelectionBorderOverlay(QWidget):
    def __init__(
        self,
        view: QTableView,
        *,
        left_edge_enabled: bool = True,
        right_edge_enabled: bool = True,
        selection_style_getter: Callable[[], str] | None = None,
    ) -> None:
        viewport = view.viewport()
        super().__init__(viewport if viewport is not None else view)
        self._view = view
        self._left_edge_enabled = left_edge_enabled
        self._right_edge_enabled = right_edge_enabled
        self._selection_style_getter = selection_style_getter

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.hide()

        self._view.destroyed.connect(self._on_view_destroyed)
        self._connect_signals()
        self._sync_geometry()

    def set_edge_visibility(self, *, left: bool, right: bool) -> None:
        if self._left_edge_enabled == left and self._right_edge_enabled == right:
            return
        self._left_edge_enabled = left
        self._right_edge_enabled = right
        self.update()

    def refresh(self) -> None:
        self._sync_geometry()
        self._update_visibility()

    def paintEvent(self, _event) -> None:
        view = self._safe_view()
        viewport = self._safe_viewport()
        if view is None or viewport is None:
            return
        if not self._should_paint():
            return

        selection = view.selectionModel()
        model = view.model()
        if selection is None or model is None or viewport is None:
            return

        top_row = view.rowAt(0)
        if top_row < 0:
            return
        bottom_row = view.rowAt(max(0, viewport.height() - 1))
        if bottom_row < 0:
            bottom_row = min(model.rowCount() - 1, top_row)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        color = selection_border_qcolor()
        thickness = 3
        viewport_width = viewport.width()

        for row in range(top_row, bottom_row + 1):
            if not selection.isRowSelected(row, QModelIndex()):
                continue

            row_height = view.rowHeight(row)
            row_top = view.rowViewportPosition(row)
            row_bottom = row_top + row_height
            prev_selected = row > 0 and selection.isRowSelected(row - 1, QModelIndex())
            next_selected = (
                row + 1 < model.rowCount()
                and selection.isRowSelected(row + 1, QModelIndex())
            )

            if self._left_edge_enabled:
                painter.fillRect(0, row_top, thickness, row_height, color)
            if self._right_edge_enabled:
                painter.fillRect(
                    viewport_width - thickness,
                    row_top,
                    thickness,
                    row_height,
                    color,
                )
            if not prev_selected:
                painter.fillRect(0, row_top, viewport_width, thickness, color)
            if not next_selected:
                painter.fillRect(
                    0,
                    row_bottom - thickness,
                    viewport_width,
                    thickness,
                    color,
                )

        painter.end()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        view = self._safe_view()
        viewport = self._safe_viewport()
        if view is not None and viewport is not None and watched in (view, viewport) and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.Hide,
        ):
            self.refresh()
        return super().eventFilter(watched, event)

    def _connect_signals(self) -> None:
        view = self._safe_view()
        viewport = self._safe_viewport()
        if view is None or viewport is None:
            return

        view.installEventFilter(self)
        viewport.installEventFilter(self)

        model = view.model()
        if model is not None:
            self._connect_model(model)

        selection = view.selectionModel()
        if selection is not None:
            selection.selectionChanged.connect(self._on_selection_changed)
            selection.currentChanged.connect(self._on_selection_changed)

        vertical_bar = view.verticalScrollBar()
        if vertical_bar is not None:
            vertical_bar.valueChanged.connect(self._on_selection_changed)
        horizontal_bar = view.horizontalScrollBar()
        if horizontal_bar is not None:
            horizontal_bar.valueChanged.connect(self._on_selection_changed)

        vertical_header = view.verticalHeader()
        if vertical_header is not None:
            vertical_header.sectionResized.connect(self._on_selection_changed)

    def _connect_model(self, model: QAbstractItemModel) -> None:
        model.modelReset.connect(self._on_selection_changed)
        model.layoutChanged.connect(self._on_selection_changed)
        model.rowsInserted.connect(self._on_selection_changed)
        model.rowsRemoved.connect(self._on_selection_changed)
        model.columnsInserted.connect(self._on_selection_changed)
        model.columnsRemoved.connect(self._on_selection_changed)
        model.dataChanged.connect(self._on_selection_changed)

    def _should_paint(self) -> bool:
        selection_style = (
            self._selection_style_getter()
            if self._selection_style_getter is not None
            else get_settings().selection_style
        )
        if selection_style != SELECTION_STYLE_BORDER:
            return False
        view = self._safe_view()
        if view is None:
            return False
        selection = view.selectionModel()
        model = view.model()
        return (
            selection is not None
            and selection.hasSelection()
            and model is not None
            and model.rowCount() > 0
        )

    def _sync_geometry(self) -> None:
        viewport = self._safe_viewport()
        if viewport is None:
            return
        if self.parentWidget() is viewport:
            self.setGeometry(viewport.rect())
        else:
            self.setGeometry(viewport.geometry())

    def _update_visibility(self) -> None:
        view = self._safe_view()
        viewport = self._safe_viewport()
        should_show = (
            self._should_paint()
            and view is not None
            and view.isVisible()
            and viewport is not None
            and viewport.isVisible()
        )
        self.setVisible(should_show)
        if should_show:
            self.raise_()
            self.update()

    def _on_selection_changed(self, *_args) -> None:
        self._update_visibility()

    def _on_view_destroyed(self, *_args) -> None:
        self._view = None

    def _safe_view(self) -> QTableView | None:
        view = _safe_qobject(self._view)
        if view is None:
            self._view = None
        return view

    def _safe_viewport(self):
        view = self._safe_view()
        if view is None:
            return None
        return _safe_qobject(view.viewport())


class FrozenColumnsController(QObject):
    def __init__(
        self,
        view: QTableView,
        main_selection_overlay: SelectionBorderOverlay,
        *,
        selection_style_getter: Callable[[], str] | None = None,
    ) -> None:
        super().__init__(view)
        self._view = view
        self._main_selection_overlay = main_selection_overlay
        self._enabled = False
        self._columns: tuple[int, ...] = ()
        self._selection_style_getter = selection_style_getter

        self._frozen_view = self._build_frozen_view()
        self._sync_model_and_selection()
        self._selection_overlay = SelectionBorderOverlay(
            self._frozen_view,
            left_edge_enabled=True,
            right_edge_enabled=False,
            selection_style_getter=selection_style_getter,
        )

        self._separator = QFrame(view)
        self._separator.setFrameShape(QFrame.Shape.NoFrame)
        self._separator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._separator.hide()

        self._view.destroyed.connect(self._on_view_destroyed)
        self._frozen_view.destroyed.connect(self._on_frozen_view_destroyed)
        self._separator.destroyed.connect(self._on_separator_destroyed)
        self._main_selection_overlay.destroyed.connect(self._on_main_overlay_destroyed)
        self._selection_overlay.destroyed.connect(self._on_selection_overlay_destroyed)
        self._connect_signals()
        self.refresh()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.refresh()

    def set_columns(self, columns: list[int]) -> None:
        unique_columns: list[int] = []
        for column in columns:
            if column >= 0 and column not in unique_columns:
                unique_columns.append(column)
        self._columns = tuple(unique_columns)
        self.refresh()

    def sync_delegate(self) -> None:
        view = self._safe_view()
        frozen_view = self._safe_frozen_view()
        if view is None or frozen_view is None:
            return
        delegate = view.itemDelegate()
        if delegate is not None:
            frozen_view.setItemDelegate(delegate)
        self.refresh()

    def refresh(self) -> None:
        if self._safe_view() is None or self._safe_frozen_view() is None:
            return
        self._sync_model_and_selection()
        self._sync_visual_state()
        self._sync_header_order()
        self._sync_columns()
        self._sync_sort_indicator()
        self._update_geometry_and_visibility()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        view = self._safe_view()
        viewport = self._safe_viewport()
        if view is not None and viewport is not None and watched in (view, viewport) and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.Hide,
        ):
            self.refresh()
        return super().eventFilter(watched, event)

    def _build_frozen_view(self) -> QTableView:
        frozen = QTableView(self._view)
        frozen.setObjectName("flagFrozenColumnsView")
        frozen.setFrameShape(QFrame.Shape.NoFrame)
        frozen.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        frozen.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        frozen.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        frozen.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        frozen.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        frozen.setSelectionBehavior(self._view.selectionBehavior())
        frozen.setSelectionMode(self._view.selectionMode())
        frozen.setWordWrap(False)
        frozen.setSortingEnabled(False)
        frozen.verticalHeader().hide()
        frozen.setVerticalScrollMode(self._view.verticalScrollMode())
        frozen.setHorizontalScrollMode(self._view.horizontalScrollMode())

        frozen_header = frozen.horizontalHeader()
        frozen_header.setHighlightSections(False)
        frozen_header.setSectionsClickable(False)
        frozen_header.setSectionsMovable(False)
        frozen_header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        frozen.hide()
        return frozen

    def _connect_signals(self) -> None:
        view = self._safe_view()
        viewport = self._safe_viewport()
        if view is None or viewport is None:
            return

        view.installEventFilter(self)
        viewport.installEventFilter(self)

        model = view.model()
        if model is not None:
            model.modelReset.connect(self._on_structure_changed)
            model.layoutChanged.connect(self._on_structure_changed)
            model.rowsInserted.connect(self._on_rows_changed)
            model.rowsRemoved.connect(self._on_rows_changed)
            model.columnsInserted.connect(self._on_structure_changed)
            model.columnsRemoved.connect(self._on_structure_changed)

        header = view.horizontalHeader()
        if header is not None:
            header.sectionResized.connect(self._on_column_resized)
            header.sectionMoved.connect(self._on_structure_changed)
            header.sortIndicatorChanged.connect(self._sync_sort_indicator)
            header.geometriesChanged.connect(self._on_structure_changed)

        vertical_header = view.verticalHeader()
        if vertical_header is not None:
            vertical_header.sectionResized.connect(self._on_row_resized)

        horizontal_bar = view.horizontalScrollBar()
        if horizontal_bar is not None:
            horizontal_bar.valueChanged.connect(self._on_horizontal_scroll)

        frozen_view = self._safe_frozen_view()
        if frozen_view is None:
            return
        view_vertical_bar = view.verticalScrollBar()
        frozen_vertical_bar = frozen_view.verticalScrollBar()
        if view_vertical_bar is not None and frozen_vertical_bar is not None:
            view_vertical_bar.valueChanged.connect(self._sync_frozen_vertical_scroll)
            frozen_vertical_bar.valueChanged.connect(self._sync_main_vertical_scroll)

        frozen_header = frozen_view.horizontalHeader()
        if frozen_header is not None:
            frozen_header.customContextMenuRequested.connect(
                self._forward_header_context_menu
            )

    def _sync_model_and_selection(self) -> None:
        view = self._safe_view()
        frozen_view = self._safe_frozen_view()
        if view is None or frozen_view is None:
            return
        model = view.model()
        if model is not None and frozen_view.model() is not model:
            frozen_view.setModel(model)

        selection = view.selectionModel()
        if selection is not None and frozen_view.selectionModel() is not selection:
            frozen_view.setSelectionModel(selection)

        delegate = view.itemDelegate()
        if delegate is not None:
            frozen_view.setItemDelegate(delegate)

    def _sync_visual_state(self) -> None:
        view = self._safe_view()
        frozen_view = self._safe_frozen_view()
        separator = self._safe_separator()
        if view is None or frozen_view is None:
            return
        palette = view.palette()
        frozen_view.setPalette(palette)
        frozen_view.setFont(view.font())
        frozen_view.setStyle(view.style())
        frozen_view.setShowGrid(view.showGrid())
        frozen_view.setGridStyle(view.gridStyle())
        frozen_view.setAlternatingRowColors(view.alternatingRowColors())
        frozen_view.setEditTriggers(view.editTriggers())

        main_header = view.horizontalHeader()
        frozen_header = frozen_view.horizontalHeader()
        main_vertical_header = view.verticalHeader()
        frozen_vertical_header = frozen_view.verticalHeader()
        if main_header is not None and frozen_header is not None:
            frozen_header.setDefaultSectionSize(main_header.defaultSectionSize())
            frozen_header.setMinimumSectionSize(main_header.minimumSectionSize())
            frozen_header.setFixedHeight(main_header.height())
            frozen_header.setFont(main_header.font())
        if main_vertical_header is not None and frozen_vertical_header is not None:
            frozen_vertical_header.setDefaultSectionSize(
                main_vertical_header.defaultSectionSize()
            )
            frozen_vertical_header.setMinimumSectionSize(
                main_vertical_header.minimumSectionSize()
            )

        if separator is not None:
            mid = palette.color(QPalette.ColorRole.Mid).name()
            separator.setStyleSheet(f"background: {mid};")

    def _sync_header_order(self) -> None:
        view = self._safe_view()
        frozen_view = self._safe_frozen_view()
        if view is None or frozen_view is None:
            return
        main_header = view.horizontalHeader()
        frozen_header = frozen_view.horizontalHeader()
        if main_header is None or frozen_header is None:
            return

        blocker = QSignalBlocker(frozen_header)
        try:
            for visual_index in range(main_header.count()):
                logical_index = main_header.logicalIndex(visual_index)
                frozen_visual = frozen_header.visualIndex(logical_index)
                if frozen_visual != visual_index and frozen_visual >= 0:
                    frozen_header.moveSection(frozen_visual, visual_index)
        finally:
            del blocker

    def _sync_columns(self) -> None:
        frozen_view = self._safe_frozen_view()
        view = self._safe_view()
        if frozen_view is None or view is None:
            return
        model = frozen_view.model()
        if model is None:
            return

        sticky_columns = set(self._visible_sticky_columns())
        for column in range(model.columnCount()):
            should_hide = column not in sticky_columns or view.isColumnHidden(column)
            frozen_view.setColumnHidden(column, should_hide)
        for column in sticky_columns:
            frozen_view.setColumnWidth(column, view.columnWidth(column))

    def _sync_sort_indicator(self, *_args) -> None:
        view = self._safe_view()
        frozen_view = self._safe_frozen_view()
        if view is None or frozen_view is None:
            return
        main_header = view.horizontalHeader()
        frozen_header = frozen_view.horizontalHeader()
        if main_header is None or frozen_header is None:
            return

        blocker = QSignalBlocker(frozen_header)
        try:
            shown = main_header.isSortIndicatorShown()
            frozen_header.setSortIndicatorShown(shown)
            if shown:
                frozen_header.setSortIndicator(
                    main_header.sortIndicatorSection(),
                    main_header.sortIndicatorOrder(),
                )
        finally:
            del blocker

    def frozen_view(self) -> QTableView | None:
        return self._safe_frozen_view()

    def sticky_active(self) -> bool:
        return self._is_active()

    def _visible_sticky_columns(self) -> tuple[int, ...]:
        view = self._safe_view()
        if view is None:
            return ()
        return tuple(
            column for column in self._columns if not view.isColumnHidden(column)
        )

    def _sticky_width(self) -> int:
        view = self._safe_view()
        if view is None:
            return 0
        return sum(view.columnWidth(column) for column in self._visible_sticky_columns())

    def _is_active(self) -> bool:
        view = self._safe_view()
        if view is None:
            return False
        horizontal_bar = view.horizontalScrollBar()
        return (
            self._enabled
            and bool(self._visible_sticky_columns())
            and horizontal_bar is not None
            and horizontal_bar.value() > 0
        )

    def _update_geometry_and_visibility(self) -> None:
        frozen_view = self._safe_frozen_view()
        separator = self._safe_separator()
        selection_overlay = self._safe_selection_overlay()
        main_selection_overlay = self._safe_main_selection_overlay()
        if not self._is_active():
            if frozen_view is not None:
                frozen_view.hide()
            if separator is not None:
                separator.hide()
            if selection_overlay is not None:
                selection_overlay.hide()
            if main_selection_overlay is not None:
                main_selection_overlay.set_edge_visibility(left=True, right=True)
                main_selection_overlay.refresh()
            return

        width = self._sticky_width()
        if width <= 0:
            if frozen_view is not None:
                frozen_view.hide()
            if separator is not None:
                separator.hide()
            if selection_overlay is not None:
                selection_overlay.hide()
            if main_selection_overlay is not None:
                main_selection_overlay.set_edge_visibility(left=True, right=True)
                main_selection_overlay.refresh()
            return

        view = self._safe_view()
        viewport = self._safe_viewport()
        if frozen_view is None or separator is None or view is None:
            return
        header = view.horizontalHeader()
        if header is None or viewport is None:
            return

        x = viewport.geometry().left()
        y = header.geometry().top()
        height = header.height() + viewport.height()
        frozen_view.setGeometry(x, y, width, height)
        separator.setGeometry(x + width - 1, y, 1, height)

        self._sync_visible_row_heights()
        self._sync_frozen_vertical_scroll()

        frozen_view.show()
        frozen_view.raise_()
        separator.show()
        separator.raise_()
        if selection_overlay is not None:
            selection_overlay.refresh()
        if main_selection_overlay is not None:
            main_selection_overlay.set_edge_visibility(left=False, right=True)
            main_selection_overlay.refresh()

    def _sync_visible_row_heights(self) -> None:
        view = self._safe_view()
        frozen_view = self._safe_frozen_view()
        viewport = self._safe_viewport()
        if view is None or frozen_view is None:
            return
        model = view.model()
        if model is None or viewport is None or model.rowCount() == 0:
            return

        top_row = view.rowAt(0)
        if top_row < 0:
            top_row = 0
        bottom_row = view.rowAt(max(0, viewport.height() - 1))
        if bottom_row < 0:
            bottom_row = min(model.rowCount() - 1, top_row)

        for row in range(top_row, bottom_row + 1):
            height = view.rowHeight(row)
            if frozen_view.rowHeight(row) != height:
                frozen_view.setRowHeight(row, height)

    def _sync_frozen_vertical_scroll(self, value: int | None = None) -> None:
        view = self._safe_view()
        frozen_view = self._safe_frozen_view()
        if view is None or frozen_view is None:
            return
        main_bar = view.verticalScrollBar()
        frozen_bar = frozen_view.verticalScrollBar()
        if main_bar is None or frozen_bar is None:
            return
        if value is None:
            value = main_bar.value()
        if frozen_bar.value() != value:
            frozen_bar.setValue(value)

    def _sync_main_vertical_scroll(self, value: int) -> None:
        view = self._safe_view()
        if view is None:
            return
        main_bar = view.verticalScrollBar()
        if main_bar is not None and main_bar.value() != value:
            main_bar.setValue(value)

    def _forward_header_context_menu(self, pos) -> None:
        view = self._safe_view()
        frozen_view = self._safe_frozen_view()
        if view is None or frozen_view is None:
            return
        main_header = view.horizontalHeader()
        frozen_header = frozen_view.horizontalHeader()
        if main_header is None or frozen_header is None:
            return

        global_pos = frozen_header.mapToGlobal(pos)
        mapped_pos = main_header.mapFromGlobal(global_pos)
        main_header.customContextMenuRequested.emit(mapped_pos)

    def _on_horizontal_scroll(self, _value: int) -> None:
        self._update_geometry_and_visibility()

    def _on_column_resized(
        self, logical_index: int, _old_size: int, new_size: int
    ) -> None:
        frozen_view = self._safe_frozen_view()
        if frozen_view is None:
            return
        if logical_index in self._visible_sticky_columns():
            frozen_view.setColumnWidth(logical_index, new_size)
            self._update_geometry_and_visibility()

    def _on_row_resized(self, row: int, _old_size: int, new_size: int) -> None:
        frozen_view = self._safe_frozen_view()
        if frozen_view is not None:
            frozen_view.setRowHeight(row, new_size)
        selection_overlay = self._safe_selection_overlay()
        if selection_overlay is not None:
            selection_overlay.update()
        main_selection_overlay = self._safe_main_selection_overlay()
        if main_selection_overlay is not None:
            main_selection_overlay.update()

    def _on_rows_changed(self, *_args) -> None:
        self._sync_visible_row_heights()
        selection_overlay = self._safe_selection_overlay()
        if selection_overlay is not None:
            selection_overlay.refresh()
        main_selection_overlay = self._safe_main_selection_overlay()
        if main_selection_overlay is not None:
            main_selection_overlay.refresh()

    def _on_structure_changed(self, *_args) -> None:
        self.refresh()

    def _on_view_destroyed(self, *_args) -> None:
        self._view = None
        self._frozen_view = None
        self._separator = None
        self._selection_overlay = None
        self._main_selection_overlay = None

    def _on_frozen_view_destroyed(self, *_args) -> None:
        self._frozen_view = None
        self._selection_overlay = None

    def _on_separator_destroyed(self, *_args) -> None:
        self._separator = None

    def _on_main_overlay_destroyed(self, *_args) -> None:
        self._main_selection_overlay = None

    def _on_selection_overlay_destroyed(self, *_args) -> None:
        self._selection_overlay = None

    def _safe_view(self) -> QTableView | None:
        view = _safe_qobject(self._view)
        if view is None:
            self._view = None
        return view

    def _safe_frozen_view(self) -> QTableView | None:
        frozen_view = _safe_qobject(self._frozen_view)
        if frozen_view is None:
            self._frozen_view = None
        return frozen_view

    def _safe_viewport(self):
        view = self._safe_view()
        if view is None:
            return None
        return _safe_qobject(view.viewport())

    def _safe_separator(self) -> QFrame | None:
        separator = _safe_qobject(self._separator)
        if separator is None:
            self._separator = None
        return separator

    def _safe_main_selection_overlay(self) -> SelectionBorderOverlay | None:
        overlay = _safe_qobject(self._main_selection_overlay)
        if overlay is None:
            self._main_selection_overlay = None
        return overlay

    def _safe_selection_overlay(self) -> SelectionBorderOverlay | None:
        overlay = _safe_qobject(self._selection_overlay)
        if overlay is None:
            self._selection_overlay = None
        return overlay

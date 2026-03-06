from __future__ import annotations

from aqt.qt import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSize,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    Qt,
)

from .config import AddonSettings, get_settings, save_settings
from .constants import (
    OUTLINE_MODE_AUTO,
    OUTLINE_MODE_BLACK,
    OUTLINE_MODE_FLAG,
    OUTLINE_MODE_WHITE,
    SELECTION_STYLE_BORDER,
    SELECTION_STYLE_CLASSIC,
)
from .painting import outline_mode_tile_icon, selection_style_tile_icon
from .preview import BrowserPreview


class FlagColumnSettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Flag Column Settings")
        self.resize(1140, 600)

        layout = QVBoxLayout(self)
        content = QHBoxLayout()
        content.setSpacing(18)
        layout.addLayout(content)

        options = QVBoxLayout()
        options.setSpacing(12)
        content.addLayout(options, 1)

        options.addWidget(QLabel("Flag outline color"))
        self._mode_buttons: dict[str, QToolButton] = {}
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        outline_tiles = QHBoxLayout()
        outline_tiles.setSpacing(8)
        for label, mode in (
            ("Auto", OUTLINE_MODE_AUTO),
            ("Black", OUTLINE_MODE_BLACK),
            ("White", OUTLINE_MODE_WHITE),
            ("Match flag", OUTLINE_MODE_FLAG),
        ):
            button = self._make_tile_button(
                label,
                outline_mode_tile_icon(mode),
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
            ("Classic fill", SELECTION_STYLE_CLASSIC),
            ("Border only", SELECTION_STYLE_BORDER),
        ):
            button = self._make_tile_button(
                label,
                selection_style_tile_icon(style),
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

        preview_column = QVBoxLayout()
        preview_title = QLabel("Browser Preview")
        preview_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._preview = BrowserPreview(self)
        preview_column.addWidget(preview_title)
        preview_column.addWidget(self._preview, 1)
        content.addLayout(preview_column, 2)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._apply_settings(get_settings())
        self._connect_preview_updates()

    def accept(self) -> None:
        save_settings(self._selected_settings())
        super().accept()

    @staticmethod
    def _make_tile_button(
        text: str,
        icon,
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

    def _connect_preview_updates(self) -> None:
        for button in self._mode_buttons.values():
            button.toggled.connect(self._sync_preview)
        for button in self._selection_buttons.values():
            button.toggled.connect(self._sync_preview)
        self._flag_border_checkbox.toggled.connect(self._sync_preview)
        self._state_icons_checkbox.toggled.connect(self._sync_preview)
        self._sticky_columns_checkbox.toggled.connect(self._sync_preview)

    def _apply_settings(self, settings: AddonSettings) -> None:
        self._mode_buttons[settings.outline_mode].setChecked(True)
        self._flag_border_checkbox.setChecked(settings.flag_border_enabled)
        self._selection_buttons[settings.selection_style].setChecked(True)
        self._state_icons_checkbox.setChecked(settings.state_icons_enabled)
        self._sticky_columns_checkbox.setChecked(settings.sticky_columns_enabled)
        self._preview.set_settings(settings)

    def _selected_outline_mode(self) -> str:
        for mode, button in self._mode_buttons.items():
            if button.isChecked():
                return mode
        return OUTLINE_MODE_FLAG

    def _selected_selection_style(self) -> str:
        for style, button in self._selection_buttons.items():
            if button.isChecked():
                return style
        return SELECTION_STYLE_CLASSIC

    def _selected_settings(self) -> AddonSettings:
        return AddonSettings(
            outline_mode=self._selected_outline_mode(),
            flag_border_enabled=self._flag_border_checkbox.isChecked(),
            selection_style=self._selected_selection_style(),
            state_icons_enabled=self._state_icons_checkbox.isChecked(),
            sticky_columns_enabled=self._sticky_columns_checkbox.isChecked(),
        )

    def _sync_preview(self, *_args) -> None:
        self._preview.set_settings(self._selected_settings())

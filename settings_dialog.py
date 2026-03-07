from __future__ import annotations

from aqt.qt import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QIcon,
    QLabel,
    QRect,
    QScrollArea,
    QSize,
    QSizePolicy,
    QSplitter,
    QStyle,
    QStyleOptionToolButton,
    QStylePainter,
    QToolButton,
    QVBoxLayout,
    QWidget,
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


class CenteredTileButton(QToolButton):
    def paintEvent(self, event) -> None:
        painter = QStylePainter(self)
        option = QStyleOptionToolButton()
        self.initStyleOption(option)

        base_option = QStyleOptionToolButton(option)
        base_option.text = ""
        base_option.icon = QIcon()
        painter.drawComplexControl(QStyle.ComplexControl.CC_ToolButton, base_option)

        contents = self.rect().adjusted(12, 10, -12, -10)
        icon_size = option.iconSize
        text_height = option.fontMetrics.height()
        spacing = 6
        block_height = icon_size.height() + spacing + text_height
        block_top = contents.top() + max(0, (contents.height() - block_height) // 2)

        icon_rect = QRect(
            contents.left() + max(0, (contents.width() - icon_size.width()) // 2),
            block_top,
            icon_size.width(),
            icon_size.height(),
        )

        icon_mode = (
            QIcon.Mode.Disabled
            if not self.isEnabled()
            else (QIcon.Mode.Active if option.state & QStyle.StateFlag.State_MouseOver else QIcon.Mode.Normal)
        )
        icon_state = QIcon.State.On if self.isChecked() else QIcon.State.Off
        option.icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter, icon_mode, icon_state)

        text_rect = QRect(
            contents.left(),
            icon_rect.bottom() + 1 + spacing,
            contents.width(),
            text_height,
        )
        painter.setPen(self.palette().buttonText().color())
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            option.text,
        )


class FlagColumnSettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Flag Column Settings")
        self.resize(1360, 690)
        self.setMinimumSize(1180, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_settings_panel())
        splitter.addWidget(self._build_preview_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([600, 760])
        layout.addWidget(splitter, 1)

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

    def _build_settings_panel(self) -> QWidget:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget(scroll)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(12)
        layout.addWidget(self._build_outline_section())
        layout.addWidget(self._build_selection_section())
        layout.addWidget(self._build_behavior_section())
        layout.addStretch(1)

        scroll.setWidget(container)
        return scroll

    def _build_preview_panel(self) -> QWidget:
        group = QGroupBox("Live Preview", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        description = self._make_supporting_label(
            "The sample browser updates immediately as you change options."
        )
        layout.addWidget(description)

        self._preview = BrowserPreview(group)
        layout.addWidget(self._preview, 1)

        return group

    def _build_outline_section(self) -> QWidget:
        group = QGroupBox("Flag Appearance", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(
            self._make_supporting_label(
                "Choose the outline treatment for the flag glyph."
            )
        )

        self._mode_buttons: dict[str, QToolButton] = {}
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)

        row = QHBoxLayout()
        row.setSpacing(8)

        for label, mode, tooltip in (
            ("Auto", OUTLINE_MODE_AUTO, "Use the theme-aware outline color."),
            ("Black", OUTLINE_MODE_BLACK, "Always draw a black outline."),
            ("White", OUTLINE_MODE_WHITE, "Always draw a white outline."),
            ("Match Flag", OUTLINE_MODE_FLAG, "Use the flag color for the outline."),
        ):
            button = self._make_tile_button(
                label,
                outline_mode_tile_icon(mode),
                icon_size=QSize(118, 54),
                minimum_height=100,
                tool_tip=tooltip,
                minimum_width=120,
            )
            self._mode_group.addButton(button)
            self._mode_buttons[mode] = button
            row.addWidget(button, 1)

        layout.addLayout(row)

        self._flag_border_checkbox = QCheckBox("Show flag border", group)
        layout.addWidget(self._flag_border_checkbox)

        return group

    def _build_selection_section(self) -> QWidget:
        group = QGroupBox("Row Selection", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(
            self._make_supporting_label(
                "Choose whether selected rows use classic fill or a lighter border treatment."
            )
        )

        self._selection_buttons: dict[str, QToolButton] = {}
        self._selection_group = QButtonGroup(self)
        self._selection_group.setExclusive(True)

        row = QHBoxLayout()
        row.setSpacing(10)

        for label, style, tooltip in (
            (
                "Classic Fill",
                SELECTION_STYLE_CLASSIC,
                "Fill selected rows using the standard selection highlight.",
            ),
            (
                "Border Only",
                SELECTION_STYLE_BORDER,
                "Keep row colors visible and outline the selected rows instead.",
            ),
        ):
            button = self._make_tile_button(
                label,
                selection_style_tile_icon(style),
                icon_size=QSize(188, 56),
                minimum_height=102,
                tool_tip=tooltip,
                minimum_width=210,
            )
            self._selection_group.addButton(button)
            self._selection_buttons[style] = button
            row.addWidget(button, 1)

        layout.addLayout(row)
        return group

    def _build_behavior_section(self) -> QWidget:
        group = QGroupBox("Browser Behavior", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(
            self._make_supporting_label(
                "These options change how the additional columns behave while you browse larger tables."
            )
        )

        self._state_icons_checkbox = QCheckBox("Show compact badges for marked, suspended, and buried cards", group)
        layout.addWidget(self._state_icons_checkbox)

        self._sticky_columns_checkbox = QCheckBox(
            "Keep Flag and State columns sticky while horizontally scrolling",
            group,
        )
        layout.addWidget(self._sticky_columns_checkbox)

        return group

    @staticmethod
    def _make_tile_button(
        text: str,
        icon,
        *,
        icon_size: QSize,
        minimum_height: int,
        tool_tip: str,
        minimum_width: int = 0,
    ) -> QToolButton:
        button = CenteredTileButton()
        button.setCheckable(True)
        button.setAutoRaise(False)
        button.setIcon(icon)
        button.setIconSize(icon_size)
        button.setText(text)
        button.setToolTip(tool_tip)
        if minimum_width > 0:
            button.setMinimumWidth(minimum_width)
        button.setMinimumHeight(minimum_height)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return button

    @staticmethod
    def _make_supporting_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return label

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

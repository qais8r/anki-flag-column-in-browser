from __future__ import annotations

from dataclasses import dataclass

import aqt

from .constants import (
    FLAG_BORDER_CONFIG_KEY,
    OUTLINE_CONFIG_KEY,
    OUTLINE_MODE_FLAG,
    OUTLINE_MODES,
    SELECTION_BORDER_LEGACY_CONFIG_KEY,
    SELECTION_STYLE_BORDER,
    SELECTION_STYLE_CLASSIC,
    SELECTION_STYLE_CONFIG_KEY,
    SELECTION_STYLES,
    STATE_ICONS_CONFIG_KEY,
    STICKY_COLUMNS_CONFIG_KEY,
)


@dataclass(frozen=True, slots=True)
class AddonSettings:
    outline_mode: str = OUTLINE_MODE_FLAG
    flag_border_enabled: bool = True
    selection_style: str = SELECTION_STYLE_CLASSIC
    state_icons_enabled: bool = False
    sticky_columns_enabled: bool = False

    def to_config(self) -> dict[str, object]:
        return {
            OUTLINE_CONFIG_KEY: self.outline_mode,
            FLAG_BORDER_CONFIG_KEY: self.flag_border_enabled,
            SELECTION_STYLE_CONFIG_KEY: self.selection_style,
            STATE_ICONS_CONFIG_KEY: self.state_icons_enabled,
            STICKY_COLUMNS_CONFIG_KEY: self.sticky_columns_enabled,
        }


_CURRENT_SETTINGS = AddonSettings()


def addon_module_name() -> str:
    package_name = __package__ or __name__
    return package_name.split(".", 1)[0]


def _sanitize_bool(value: object, fallback: bool) -> bool:
    return value if isinstance(value, bool) else fallback


def _sanitize_settings(raw_config: dict[str, object] | None) -> AddonSettings:
    config = raw_config or {}
    defaults = AddonSettings()

    outline_mode = config.get(OUTLINE_CONFIG_KEY, defaults.outline_mode)
    if outline_mode not in OUTLINE_MODES:
        outline_mode = defaults.outline_mode

    selection_style = config.get(SELECTION_STYLE_CONFIG_KEY)
    if selection_style not in SELECTION_STYLES:
        legacy = config.get(SELECTION_BORDER_LEGACY_CONFIG_KEY)
        if isinstance(legacy, bool):
            selection_style = (
                SELECTION_STYLE_BORDER if legacy else SELECTION_STYLE_CLASSIC
            )
        else:
            selection_style = defaults.selection_style

    return AddonSettings(
        outline_mode=outline_mode,
        flag_border_enabled=_sanitize_bool(
            config.get(FLAG_BORDER_CONFIG_KEY), defaults.flag_border_enabled
        ),
        selection_style=selection_style,
        state_icons_enabled=_sanitize_bool(
            config.get(STATE_ICONS_CONFIG_KEY), defaults.state_icons_enabled
        ),
        sticky_columns_enabled=_sanitize_bool(
            config.get(STICKY_COLUMNS_CONFIG_KEY), defaults.sticky_columns_enabled
        ),
    )


def get_settings() -> AddonSettings:
    return _CURRENT_SETTINGS


def refresh_settings() -> AddonSettings:
    global _CURRENT_SETTINGS
    if aqt.mw is None:
        _CURRENT_SETTINGS = AddonSettings()
        return _CURRENT_SETTINGS

    config = aqt.mw.addonManager.getConfig(addon_module_name())
    _CURRENT_SETTINGS = _sanitize_settings(config)
    return _CURRENT_SETTINGS


def save_settings(settings: AddonSettings) -> AddonSettings:
    global _CURRENT_SETTINGS
    sanitized = _sanitize_settings(settings.to_config())
    _CURRENT_SETTINGS = sanitized
    if aqt.mw is None:
        return sanitized

    config = aqt.mw.addonManager.getConfig(addon_module_name()) or {}
    desired = sanitized.to_config()
    if all(config.get(key) == value for key, value in desired.items()):
        return sanitized

    config.update(desired)
    aqt.mw.addonManager.writeConfig(addon_module_name(), config)
    return sanitized

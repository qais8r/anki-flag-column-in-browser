from __future__ import annotations

from dataclasses import dataclass

import aqt

OUTLINE_CONFIG_KEY = "flag_outline"
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

STATE_PREFIXES_CONFIG_KEY = "show_state_prefixes_in_sort_field"
DEFAULT_SHOW_STATE_PREFIXES = True


@dataclass(frozen=True)
class AddonSettings:
    outline_mode: str = OUTLINE_MODE_AUTO
    show_state_prefixes_in_sort_field: bool = DEFAULT_SHOW_STATE_PREFIXES

    def to_config(self) -> dict[str, object]:
        return {
            OUTLINE_CONFIG_KEY: self.outline_mode,
            STATE_PREFIXES_CONFIG_KEY: self.show_state_prefixes_in_sort_field,
        }


_CURRENT_SETTINGS = AddonSettings()


def addon_module_name() -> str:
    return (__package__ or __name__).split(".", 1)[0]


def get_settings() -> AddonSettings:
    return _CURRENT_SETTINGS


def refresh_settings() -> AddonSettings:
    global _CURRENT_SETTINGS
    if aqt.mw is None:
        _CURRENT_SETTINGS = AddonSettings()
        return _CURRENT_SETTINGS
    config = aqt.mw.addonManager.getConfig(addon_module_name()) or {}
    _CURRENT_SETTINGS = _sanitize_settings(config)
    return _CURRENT_SETTINGS


def save_settings(settings: AddonSettings) -> AddonSettings:
    global _CURRENT_SETTINGS
    sanitized = _sanitize_settings(settings.to_config())
    _CURRENT_SETTINGS = sanitized
    if aqt.mw is None:
        return sanitized

    config = (aqt.mw.addonManager.getConfig(addon_module_name()) or {}).copy()
    updated_config = config.copy()
    updated_config.update(sanitized.to_config())
    if updated_config == config:
        return sanitized

    aqt.mw.addonManager.writeConfig(addon_module_name(), updated_config)
    return sanitized


def _sanitize_settings(raw_config: dict[str, object] | None) -> AddonSettings:
    raw_config = raw_config or {}

    outline_mode = raw_config.get(OUTLINE_CONFIG_KEY, OUTLINE_MODE_AUTO)
    if outline_mode not in OUTLINE_MODES:
        outline_mode = OUTLINE_MODE_AUTO

    show_state_prefixes = raw_config.get(
        STATE_PREFIXES_CONFIG_KEY, DEFAULT_SHOW_STATE_PREFIXES
    )
    if not isinstance(show_state_prefixes, bool):
        show_state_prefixes = DEFAULT_SHOW_STATE_PREFIXES

    return AddonSettings(
        outline_mode=outline_mode,
        show_state_prefixes_in_sort_field=show_state_prefixes,
    )

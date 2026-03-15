from __future__ import annotations

__name__ = "Flag Column in Browser"
__author__ = "Qaisar"
__version__ = "1.3"
__description__ = "Shows a flag indicator column in the Anki Browser."

import aqt
from aqt import gui_hooks

from .addon_config import addon_module_name, refresh_settings
from .browser_features import install_hooks, refresh_browser_view
from .settings_dialog import setup_config_menu


def _on_config_updated(*_args, **_kwargs) -> None:
    refresh_settings()
    refresh_browser_view(force_refetch=True)


def _on_profile_did_open() -> None:
    refresh_settings()
    setup_config_menu()
    if aqt.mw is None:
        return
    aqt.mw.addonManager.setConfigUpdatedAction(addon_module_name(), _on_config_updated)


install_hooks()
gui_hooks.profile_did_open.append(_on_profile_did_open)

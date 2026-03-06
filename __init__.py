from __future__ import annotations

from .addon import register_hooks
from .constants import (
    ADDON_AUTHOR as __author__,
    ADDON_DESCRIPTION as __description__,
    ADDON_NAME as __name__,
    ADDON_VERSION as __version__,
)

register_hooks()

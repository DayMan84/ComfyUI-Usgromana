"""
NSFW filtering for gallery and ComfyUI Assets — independent of assets visibility.

Assets visibility (Default UI: user_specific / allow_all / disable_all) controls
which users' files may appear. This module only applies per-user SFW policy
(Users tab → SFW checkbox / guest always filtered).
"""

from __future__ import annotations

import os
from typing import Any, Sequence


def is_nsfw_filter_active() -> bool:
    """True when the current session user must not see NSFW media."""
    try:
        from .sfw_intercept.nsfw_guard import is_sfw_enforced_for_current_session

        return bool(is_sfw_enforced_for_current_session(quiet=True))
    except Exception:
        return False


def should_hide_media_path(path: str | None) -> bool:
    """True if this file must not be shown to the current user (NSFW + SFW enforced)."""
    if not path or not os.path.isfile(path):
        return False
    if not is_nsfw_filter_active():
        return False
    try:
        from .sfw_intercept.nsfw_guard import should_block_image_for_current_user

        return bool(should_block_image_for_current_user(path, quiet=True))
    except Exception:
        return False


def _asset_file_path(item: Any) -> str | None:
    ref = getattr(item, "ref", None)
    if ref is None:
        return None
    return getattr(ref, "file_path", None)


def filter_nsfw_asset_items(items: Sequence[Any]) -> list[Any]:
    """Drop asset rows whose on-disk file is NSFW for the current user."""
    if not is_nsfw_filter_active():
        return list(items)
    return [item for item in items if not should_hide_media_path(_asset_file_path(item))]


def asset_detail_is_nsfw_blocked(detail: Any | None) -> bool:
    if not detail:
        return False
    return should_hide_media_path(getattr(detail.ref, "file_path", None))


def asset_download_is_nsfw_blocked(result: Any | None) -> bool:
    if not result:
        return False
    return should_hide_media_path(getattr(result, "abs_path", None))

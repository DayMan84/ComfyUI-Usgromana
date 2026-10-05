"""Glue between the share store and the running ComfyUI output directory."""

from __future__ import annotations

import os
from urllib.parse import quote

from ..constants import CURRENT_DIR
from .image_shares import ImageShareStore
from .media_paths import global_output_directory

_store: ImageShareStore | None = None


def get_share_store() -> ImageShareStore:
    global _store
    if _store is None:
        _store = ImageShareStore(
            os.path.join(CURRENT_DIR, "users", "image_shares.json"),
            global_output_directory(),
        )
    return _store


def reset_share_store() -> None:
    """Drop the cached store. Tests and output-root changes call this."""
    global _store
    _store = None


def shared_file_response_path(
    filename: str | None,
    viewer_user_id: str | None,
    viewer_username: str | None,
) -> str | None:
    """Resolve a ``shared/<owner>/<path>`` gallery filename the viewer may open.

    Returns None when the filename is not a share reference.
    Raises PermissionError when it is a share reference the viewer cannot open.
    """
    from .image_shares import parse_shared_relpath

    parsed = parse_shared_relpath(filename)
    if parsed is None:
        return None
    owner_id, relpath = parsed
    store = get_share_store()
    if not store.can_view(viewer_user_id, viewer_username, owner_id, relpath):
        raise PermissionError("Access denied")
    path = store.resolve_owned_file(owner_id, relpath)
    if not path:
        raise FileNotFoundError(relpath)
    return path


def gallery_entries_shared_with(viewer_user_id: str | None, viewer_username: str | None) -> list[dict]:
    """Gallery list rows for images other users have shared with this account."""
    if not viewer_username:
        return []
    store = get_share_store()
    rows = []
    for item in store.shares_for_viewer(viewer_username):
        if viewer_user_id and item["owner_id"] == viewer_user_id:
            continue
        rel = item["shared_relpath"]
        quoted = quote(rel, safe="")
        rows.append(
            {
                "filename": item["filename"],
                "relpath": rel,
                "size": item["size"],
                "mtime": item["mtime"],
                "folder": "Shared with you",
                "shared": True,
                "owner_id": item["owner_id"],
                "url": f"/usgromana-gallery/image?filename={quoted}",
                "thumb_url": f"/usgromana-gallery/image?filename={quoted}&size=thumb",
            }
        )
    return rows

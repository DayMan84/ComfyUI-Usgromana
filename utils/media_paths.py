"""Resolve image paths against global Comfy input/output roots (not per-user chroots)."""

from __future__ import annotations

import os

from ..globals import access_control


def global_output_directory() -> str:
    return os.path.abspath(access_control._AccessControl__get_output_directory())


def global_input_directory() -> str:
    return os.path.abspath(access_control._AccessControl__get_input_directory())


def global_temp_directory() -> str:
    return os.path.abspath(access_control._AccessControl__get_temp_directory())


def resolve_output_file_path(
    filename: str | None,
    subfolder: str | None = None,
) -> str | None:
    """
    Find an output image on disk. Tries global output/ first (gallery, assets DB paths),
    then per-user output/<user_id>/ when a user context is set.
    """
    if not filename:
        return None

    base = global_output_directory()
    sub = (subfolder or "").replace("\\", "/").strip("/")
    name = filename.replace("\\", "/").strip("/")

    candidates: list[str] = []
    if sub:
        candidates.append(os.path.join(base, sub, name))
    candidates.append(os.path.join(base, name))

    uid = access_control.get_current_user_id()
    if uid:
        candidates.append(os.path.join(base, uid, name))
        if sub and not sub.split("/")[0] == uid:
            candidates.append(os.path.join(base, uid, sub, name))

    seen: set[str] = set()
    for path in candidates:
        norm = os.path.normpath(path)
        if norm in seen:
            continue
        seen.add(norm)
        if os.path.isfile(norm):
            return norm
    return None


def _is_under(path: str, base: str) -> bool:
    path_abs = os.path.normcase(os.path.abspath(path))
    base_abs = os.path.normcase(os.path.abspath(base))
    return path_abs == base_abs or path_abs.startswith(base_abs + os.sep)


def resolve_static_gallery_path(relative_path: str) -> str | None:
    """Map /static_gallery/<rel> to a file under global output/."""
    rel = (relative_path or "").replace("\\", "/").strip("/")
    if not rel or ".." in rel.split("/"):
        return None
    base = global_output_directory()
    candidate = os.path.normpath(os.path.join(base, rel))
    if not _is_under(candidate, base):
        return None
    return candidate if os.path.isfile(candidate) else None

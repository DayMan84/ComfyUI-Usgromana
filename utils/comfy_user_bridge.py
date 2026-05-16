"""
Bridge Usgromana JWT users to ComfyUI multi-user / assets APIs.

ComfyUI's Assets tab uses UserManager.get_request_user_id() (comfy-user header)
and owner_id on asset references. Usgromana authenticates via JWT and stores
files under per-user input/output/temp subfolders.
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from typing import Callable, Iterator

import folder_paths
from aiohttp import web

from ..constants import SEPARATE_USERS
from .media_paths import (
    gallery_scan_folder_paths,
    global_input_directory,
    global_output_directory,
    global_temp_directory,
)
from ..globals import access_control
from .nsfw_media_filter import (
    asset_detail_is_nsfw_blocked,
    asset_download_is_nsfw_blocked,
    filter_nsfw_asset_items,
    is_nsfw_filter_active,
)
from .ui_defaults import (
    ASSETS_VISIBILITY_ALLOW_ALL,
    ASSETS_VISIBILITY_DISABLE_ALL,
    ASSETS_VISIBILITY_USER_SPECIFIC,
    get_assets_imports_visibility,
)

_log = logging.getLogger("usgromana.assets")

_user_manager_patched = False
_last_global_asset_sync = 0.0
_last_output_index_sync = 0.0
GLOBAL_ASSET_SYNC_INTERVAL_SEC = 45
OUTPUT_INDEX_INTERVAL_SEC = 20
ALLOW_ALL_OUTPUT_WALK_MAX = 50000
_OUTPUT_TAG_BACKFILL_MAX = 25000
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".tif"}
_SKIP_ASSET_DIR_NAMES = {"_thumbs"}
_GENERATED_EXCLUDE_TAGS = ("_thumbs", "missing")


def _is_thumb_asset_path(path: str | None) -> bool:
    if not path:
        return False
    norm = path.replace("\\", "/").lower()
    return "/_thumbs/" in norm or norm.endswith("/_thumbs")


def _list_kwargs_for_generated(kwargs: dict) -> dict:
    """Generated tab should list full images, not ComfyUI preview thumbnails."""
    include_tags = kwargs.get("include_tags") or []
    tag_list = [
        (t.lower() if isinstance(t, str) else str(t).lower()) for t in include_tags
    ]
    if "output" not in tag_list:
        return kwargs
    merged = dict(kwargs)
    exclude = list(merged.get("exclude_tags") or [])
    exclude_lower = {t.lower() if isinstance(t, str) else str(t).lower() for t in exclude}
    for tag in _GENERATED_EXCLUDE_TAGS:
        if tag not in exclude_lower:
            exclude.append(tag)
    merged["exclude_tags"] = exclude
    return merged


def _normalize_asset_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def _path_lookup_variants(path: str) -> list[str]:
    """Paths to try when matching asset_references.file_path (slash/case differences)."""
    abs_path = os.path.abspath(path)
    variants = [abs_path]
    if os.sep == "\\":
        variants.append(abs_path.replace("/", "\\"))
        variants.append(abs_path.replace("\\", "/"))
    else:
        variants.append(abs_path.replace("\\", "/"))
    seen: set[str] = set()
    ordered: list[str] = []
    for p in variants:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered


def _modules_using_owner_clause() -> list:
    """Modules that bind build_visible_owner_clause at import time."""
    mods = []
    for name in (
        "app.assets.database.queries.common",
        "app.assets.database.queries.asset_reference",
        "app.assets.database.queries.tags",
    ):
        try:
            import importlib

            mods.append(importlib.import_module(name))
        except ImportError:
            continue
    return mods


@contextmanager
def _all_owners_visible() -> Iterator[None]:
    """
    Allow SQL asset queries to see every owner_id.

    Patching only queries.common is insufficient: asset_reference.py imports
    build_visible_owner_clause by value at module load.
    """
    import sqlalchemy as sa

    saved: list[tuple[object, Callable]] = []
    for mod in _modules_using_owner_clause():
        orig = getattr(mod, "build_visible_owner_clause", None)
        if orig is not None:
            saved.append((mod, orig))
            mod.build_visible_owner_clause = lambda _owner_id: sa.true()  # noqa: ARG005
    try:
        yield
    finally:
        for mod, orig in saved:
            mod.build_visible_owner_clause = orig


def _global_output_root() -> str:
    return global_output_directory()


def _global_input_root() -> str:
    return global_input_directory()


def _owner_id_from_storage_path(abs_path: str, base_root: str) -> str:
    """
    Infer Comfy asset owner_id from path under global input/output.
    Root-level files (e.g. output/ComfyUI_00001_.png) use owner_id=''.
    """
    norm_path = os.path.normpath(os.path.abspath(abs_path))
    base = os.path.normpath(os.path.abspath(base_root))
    try:
        rel = os.path.relpath(norm_path, base).replace("\\", "/")
    except ValueError:
        return ""
    if rel.startswith(".."):
        return ""
    parts = [p for p in rel.split("/") if p]
    if len(parts) < 2:
        return ""

    first = parts[0]
    if first in _SKIP_ASSET_DIR_NAMES or first.startswith("_"):
        return ""

    manager = _get_user_manager()
    if manager is not None:
        try:
            if first in manager.users:
                return first
        except Exception:
            pass

    if len(first) == 36 and first.count("-") == 4:
        return first
    if first == "public":
        return "public"
    return ""


def _get_user_manager():
    try:
        from server import PromptServer

        instance = PromptServer.instance
        return getattr(instance, "user_manager", None)
    except Exception:
        return None


def get_comfy_user_id_for_request(request) -> str | None:
    """Resolve the ComfyUI user id for the current HTTP request."""
    if request is not None:
        header_user = request.headers.get("Comfy-User") or request.headers.get(
            "comfy-user"
        )
        if header_user:
            return header_user.strip()

    uid = access_control.get_current_user_id()
    if uid:
        return uid

    if request is not None:
        token_user = request.get("user_id")
        if token_user:
            return str(token_user)

    return None


def _user_output_dir(user_id: str) -> str:
    prev = access_control.get_current_user_id()
    try:
        access_control.set_current_user_id(user_id)
        return os.path.abspath(access_control.get_user_output_directory())
    finally:
        if prev:
            access_control.set_current_user_id(prev, set_fallback=True)


def _user_input_dir(user_id: str) -> str:
    prev = access_control.get_current_user_id()
    try:
        access_control.set_current_user_id(user_id)
        return os.path.abspath(access_control.get_user_input_directory())
    finally:
        if prev:
            access_control.set_current_user_id(prev, set_fallback=True)


def path_belongs_to_user(abs_path: str | None, user_id: str | None) -> bool:
    """True if file lives under this user's output/input/temp area."""
    if not abs_path or not user_id:
        return False
    norm_path = os.path.normpath(os.path.abspath(abs_path))

    for prefix in access_control.get_user_storage_prefixes(user_id):
        norm_prefix = os.path.normpath(prefix)
        if norm_path == norm_prefix or norm_path.startswith(norm_prefix + os.sep):
            return True

    # Legacy layouts: output/<user_id>/... under the global ComfyUI output folder.
    for base_getter in (
        access_control._AccessControl__get_output_directory,
        access_control._AccessControl__get_input_directory,
        access_control._AccessControl__get_temp_directory,
    ):
        base = os.path.abspath(base_getter())
        try:
            rel = os.path.relpath(norm_path, base).replace("\\", "/")
        except ValueError:
            continue
        if rel.startswith(".."):
            continue
        first = rel.split("/")[0]
        if first == user_id:
            return True

    # Patched per-user output root (files saved directly into output/<user_id>/).
    try:
        user_out = _user_output_dir(user_id)
        if norm_path == user_out or norm_path.startswith(user_out + os.sep):
            return True
    except Exception:
        pass

    try:
        user_in = _user_input_dir(user_id)
        if norm_path == user_in or norm_path.startswith(user_in + os.sep):
            return True
    except Exception:
        pass

    return False


def _item_visible_to_user(item, owner_id: str) -> bool:
    """Decide if an asset row belongs to the current user (generated or imported)."""
    if not owner_id:
        return False

    ref_owner = (getattr(item.ref, "owner_id", None) or "").strip()
    if ref_owner and ref_owner == owner_id:
        return True
    if ref_owner and ref_owner != owner_id:
        return False

    fp = getattr(item.ref, "file_path", None)
    if fp and path_belongs_to_user(fp, owner_id):
        return True

    tags = [t.lower() if isinstance(t, str) else t for t in (item.tags or [])]
    if "output" in tags and fp and _path_under_global_output(fp):
        if path_belongs_to_user(fp, owner_id) or ref_owner == owner_id:
            return True
    if owner_id in tags or owner_id.lower() in [str(t).lower() for t in tags]:
        return True

    meta = getattr(item.ref, "user_metadata", None) or {}
    filename = (meta.get("filename") or "").replace("\\", "/")
    if filename.startswith(f"{owner_id}/"):
        return True

    return False


def _detail_visible_to_user(detail, owner_id: str) -> bool:
    if not detail:
        return False
    return _item_visible_to_user(
        type("Row", (), {"ref": detail.ref, "tags": detail.tags})(),
        owner_id,
    )


def register_outputs_from_history(history_result: dict, user_id: str) -> None:
    """Register image outputs from a completed prompt into the assets DB."""
    if not history_result or not user_id:
        return
    try:
        from app.assets.services.ingest import ingest_existing_file
    except ImportError:
        return

    access_control.set_current_user_id(user_id, set_fallback=True)
    output_base = _global_output_root()

    outputs = history_result.get("outputs") or {}
    seen: set[str] = set()

    for node_out in outputs.values():
        if not isinstance(node_out, dict):
            continue
        for key in ("images", "gifs"):
            for img in node_out.get(key) or []:
                if not isinstance(img, dict):
                    continue
                filename = img.get("filename")
                if not filename or filename in seen:
                    continue
                seen.add(filename)
                subfolder = (img.get("subfolder") or "").strip().replace("\\", "/")
                parts = [p for p in [subfolder, filename] if p]
                rel = "/".join(parts)
                full = os.path.normpath(os.path.join(output_base, rel))
                if not os.path.isfile(full):
                    continue
                try:
                    ingest_existing_file(full, owner_id=user_id)
                except Exception as e:
                    _log.debug("register output %s: %s", full, e)


def _sync_user_input_assets(user_id: str, max_files: int = 200) -> None:
    """Register on-disk files under input/<user_id>/ into the assets DB."""
    if not user_id:
        return
    try:
        from app.assets.services.ingest import ingest_existing_file
    except ImportError:
        return

    access_control.set_current_user_id(user_id)
    user_dir = os.path.abspath(folder_paths.get_input_directory())
    if not os.path.isdir(user_dir):
        return

    count = 0
    for dirpath, _, filenames in os.walk(user_dir):
        for name in filenames:
            if os.path.splitext(name)[1].lower() not in _IMAGE_EXT:
                continue
            full = os.path.join(dirpath, name)
            try:
                access_control.set_current_user_id(user_id)
                ingest_existing_file(full, owner_id=user_id)
                count += 1
            except Exception as e:
                _log.debug("ingest input %s: %s", full, e)
            if count >= max_files:
                break
        if count >= max_files:
            break


def _get_reference_by_path(session, path: str):
    from app.assets.database.queries import get_reference_by_file_path

    for variant in _path_lookup_variants(path):
        ref = get_reference_by_file_path(session, variant)
        if ref is not None:
            return ref
    return None


def _resolve_output_file_for_asset(stored_path: str | None) -> str | None:
    """Find on-disk file for a DB path (exact path, then by filename under output/)."""
    if not stored_path:
        return None
    for variant in _path_lookup_variants(stored_path):
        if os.path.isfile(variant):
            return variant
    from .media_paths import resolve_output_file_path

    base = os.path.basename(stored_path.replace("\\", "/"))
    if base:
        return resolve_output_file_path(base, "")
    return None


def _purge_thumb_asset_references() -> int:
    """Remove asset rows that point at output/_thumbs/ (preview files, not generations)."""
    try:
        from sqlalchemy import select

        from app.database.db import create_session
        from app.assets.database.models import AssetReference
        from app.assets.database.queries import delete_references_by_ids
    except ImportError:
        return 0

    removed = 0
    try:
        with create_session() as session:
            rows = session.execute(
                select(AssetReference.id, AssetReference.file_path).where(
                    AssetReference.file_path.isnot(None)
                )
            ).all()
            to_delete = [
                ref_id
                for ref_id, fp in rows
                if fp and _is_thumb_asset_path(fp)
            ]
            if to_delete:
                removed = delete_references_by_ids(session, to_delete)
                session.commit()
    except Exception as e:
        _log.debug("purge thumb assets: %s", e)
        return removed

    if removed:
        print(f"[Usgromana::Assets] Removed {removed} thumbnail asset row(s) from DB")
        _log.info("Removed %s asset row(s) under output/_thumbs/", removed)
    return removed


def _force_register_output_file(full: str, owner_id: str = "", user_id: str | None = None) -> None:
    """Register or repair one output image (tags + owner) for the Generated tab."""
    locator = os.path.abspath(full)
    if not os.path.isfile(locator) or _is_thumb_asset_path(locator):
        return
    tags = _tags_for_output_file(locator)
    if user_id:
        access_control.set_current_user_id(user_id, set_fallback=True)
    try:
        from app.assets.services.ingest import ingest_existing_file

        ingest_existing_file(locator, owner_id=owner_id, extra_tags=tags)
    except Exception as e:
        _log.debug("ingest %s: %s", locator, e)
    _refresh_asset_tags_from_path(locator)
    if user_id:
        _claim_output_asset_owner(locator, owner_id or user_id)


def _sync_tree_into_assets(
    base_root: str,
    max_files: int = 2500,
    *,
    default_owner: str | None = None,
    user_id: str | None = None,
    output_only: bool = False,
) -> int:
    """Walk global input/output and register images (allow-all / shared visibility)."""
    if not base_root or not os.path.isdir(base_root):
        return 0

    root = os.path.abspath(base_root)
    is_output_root = _normalize_asset_path(root) == _normalize_asset_path(
        _global_output_root()
    )
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in _SKIP_ASSET_DIR_NAMES and not d.startswith("_")
        ]
        for name in filenames:
            if os.path.splitext(name)[1].lower() not in _IMAGE_EXT:
                continue
            full = os.path.join(dirpath, name)
            owner = _owner_id_from_storage_path(full, root)
            if owner == "" and default_owner:
                owner = default_owner
            try:
                if is_output_root or output_only:
                    _force_register_output_file(
                        full, owner_id=owner, user_id=user_id
                    )
                else:
                    from app.assets.services.ingest import ingest_existing_file

                    ingest_existing_file(full, owner_id=owner)
                    _refresh_asset_tags_from_path(full)
                count += 1
            except Exception as e:
                _log.debug("ingest %s: %s", full, e)
            if count >= max_files:
                return count
    return count


def _backfill_missing_output_tags(max_refs: int = _OUTPUT_TAG_BACKFILL_MAX) -> int:
    """
    Repair DB rows that live under output/ but lack the ``output`` tag.

    Comfy's asset seeder skips paths already in the DB (no tag update), so older
  seeded images never appear in the Generated tab until tags are fixed here.
    """
    try:
        import sqlalchemy as sa
        from sqlalchemy import exists, select

        from app.database.db import create_session
        from app.assets.database.models import AssetReference, AssetReferenceTag
        from app.assets.database.queries import ensure_tags_exist, set_reference_tags
    except ImportError:
        return 0

    updated = 0
    try:
        with create_session() as session:
            stmt = (
                select(AssetReference.id, AssetReference.file_path)
                .where(AssetReference.file_path.isnot(None))
                .where(AssetReference.deleted_at.is_(None))
                .where(AssetReference.is_missing == False)  # noqa: E712
                .where(
                    ~exists().where(
                        (AssetReferenceTag.asset_reference_id == AssetReference.id)
                        & (AssetReferenceTag.tag_name == "output")
                    )
                )
                .limit(max_refs)
            )
            rows = session.execute(stmt).all()
            refs_to_delete: list[str] = []
            with session.no_autoflush:
                for ref_id, file_path in rows:
                    if not file_path or ref_id in refs_to_delete:
                        continue
                    live_path = _resolve_output_file_for_asset(file_path)
                    if not live_path or not _path_under_global_output(live_path):
                        continue
                    tags = _tags_for_output_file(live_path)
                    if not tags or "output" not in [t.lower() for t in tags]:
                        continue
                    ref = session.get(AssetReference, ref_id)
                    if ref is None:
                        continue
                    canonical = _get_reference_by_path(session, live_path)
                    if canonical is not None and canonical.id != ref.id:
                        refs_to_delete.append(ref_id)
                        ref_id = canonical.id
                        ref = canonical
                    elif _normalize_asset_path(
                        ref.file_path or ""
                    ) != _normalize_asset_path(live_path):
                        if _get_reference_by_path(session, live_path):
                            refs_to_delete.append(ref_id)
                            continue
                        ref.file_path = live_path
                    ref.is_missing = False
                    ensure_tags_exist(session, tags)
                    set_reference_tags(
                        session,
                        reference_id=ref_id,
                        tags=tags,
                        origin="automatic",
                    )
                    updated += 1
            if refs_to_delete:
                from app.assets.database.queries import delete_references_by_ids

                delete_references_by_ids(session, list(dict.fromkeys(refs_to_delete)))
            if updated:
                session.commit()
    except Exception as e:
        _log.warning("Output tag backfill failed: %s", e)
        return updated

    if updated:
        _log.info("Backfilled output tag on %s existing asset(s)", updated)
    return updated


def _clear_missing_flag_for_path(abs_path: str) -> bool:
    """Unset is_missing when the file exists (Generated tab hides missing rows)."""
    if not abs_path or not os.path.isfile(abs_path):
        return False
    try:
        from app.database.db import create_session
        from app.assets.database.queries import bulk_update_is_missing
    except ImportError:
        return False

    locator = os.path.abspath(abs_path)
    try:
        with create_session() as session:
            ref = _get_reference_by_path(session, locator)
            if ref is None or not ref.is_missing:
                return False
            bulk_update_is_missing(session, [ref.id], value=False)
            session.commit()
            return True
    except Exception as e:
        _log.debug("clear missing %s: %s", locator, e)
        return False


def _repair_single_output_reference(
    session,
    ref,
    live: str,
    stats: dict[str, int],
    *,
    to_clear_missing: list[str],
    refs_to_delete: list[str],
) -> None:
    """
    Point one DB row at *live* without violating UNIQUE(file_path).

    When another row already owns *live*, drop this duplicate and repair the owner.
    """
    from app.assets.database.queries import ensure_tags_exist, set_reference_tags

    live_abs = os.path.abspath(live)
    live_norm = _normalize_asset_path(live_abs)
    stored_norm = _normalize_asset_path(ref.file_path or "")

    canonical = _get_reference_by_path(session, live_abs)
    if canonical is not None and canonical.id != ref.id:
        refs_to_delete.append(ref.id)
        ref = canonical
        stored_norm = _normalize_asset_path(ref.file_path or "")
    elif stored_norm != live_norm:
        conflict = _get_reference_by_path(session, live_abs)
        if conflict is not None and conflict.id != ref.id:
            refs_to_delete.append(ref.id)
            return
        ref.file_path = live_abs
        stats["paths_fixed"] += 1

    if ref.id in refs_to_delete:
        return

    if ref.is_missing:
        to_clear_missing.append(ref.id)

    tags = _tags_for_output_file(live_abs)
    if tags:
        ensure_tags_exist(session, tags)
        set_reference_tags(
            session,
            reference_id=ref.id,
            tags=tags,
            origin="automatic",
        )
        stats["tags_updated"] += 1


def _repair_output_asset_registry(user_id: str | None = None) -> dict[str, int]:
    """
    Full repair for Comfy Generated tab: register on-disk output files, fix tags,
    and clear is_missing when files still exist (seeder skips do not do this).
    """
    stats = {
        "disk_registered": 0,
        "missing_cleared": 0,
        "tags_updated": 0,
        "paths_fixed": 0,
        "duplicates_removed": 0,
    }
    root = _global_output_root()
    if not os.path.isdir(root):
        return stats

    stats["duplicates_removed"] += _purge_thumb_asset_references()
    stats["disk_registered"] = _sync_tree_into_assets(
        root,
        max_files=ALLOW_ALL_OUTPUT_WALK_MAX,
        output_only=True,
        user_id=user_id,
    )
    stats["tags_updated"] += _backfill_missing_output_tags()

    try:
        from sqlalchemy import select

        from app.database.db import create_session
        from app.assets.database.models import AssetReference
        from app.assets.database.queries import (
            bulk_update_is_missing,
            delete_references_by_ids,
        )
    except ImportError:
        return stats

    out_norm = _normalize_asset_path(root) + os.sep
    try:
        with create_session() as session:
            rows = session.execute(
                select(AssetReference).where(AssetReference.file_path.isnot(None))
            ).scalars().all()
            to_clear_missing: list[str] = []
            refs_to_delete: list[str] = []
            seen_delete: set[str] = set()

            with session.no_autoflush:
                for ref in rows:
                    stored = ref.file_path
                    if not stored or ref.id in seen_delete:
                        continue
                    if not _normalize_asset_path(stored).startswith(out_norm):
                        continue
                    live = _resolve_output_file_for_asset(stored)
                    if not live:
                        continue
                    before = len(refs_to_delete)
                    _repair_single_output_reference(
                        session,
                        ref,
                        live,
                        stats,
                        to_clear_missing=to_clear_missing,
                        refs_to_delete=refs_to_delete,
                    )
                    for rid in refs_to_delete[before:]:
                        seen_delete.add(rid)

            refs_to_delete = list(dict.fromkeys(refs_to_delete))
            if refs_to_delete:
                stats["duplicates_removed"] = delete_references_by_ids(
                    session, refs_to_delete
                )
            if to_clear_missing:
                bulk_update_is_missing(session, to_clear_missing, value=False)
                stats["missing_cleared"] = len(to_clear_missing)
            session.commit()
    except Exception as e:
        _log.warning("Output asset registry repair failed: %s", e)

    if any(stats.values()):
        print(
            f"[Usgromana::Assets] Repaired output registry under {root}: "
            f"registered={stats['disk_registered']} tags={stats['tags_updated']} "
            f"missing_cleared={stats['missing_cleared']} paths_fixed={stats['paths_fixed']} "
            f"duplicates_removed={stats['duplicates_removed']}"
        )
        _log.info("Output asset registry repair: %s", stats)
    return stats


_output_repair_scheduled = False
_thumb_purge_done = False


def schedule_output_registry_repair() -> None:
    """Run output registry repair once in a background thread (after admin toggle)."""
    global _output_repair_scheduled
    if _output_repair_scheduled:
        return
    _output_repair_scheduled = True

    import threading

    def _run() -> None:
        try:
            time.sleep(2.0)
            install_comfy_user_bridge()
            _repair_output_asset_registry()
        except Exception as e:
            _log.warning("Background output registry repair failed: %s", e)
        finally:
            global _output_repair_scheduled
            _output_repair_scheduled = False

    threading.Thread(target=_run, name="usgromana-output-repair", daemon=True).start()


def reset_global_asset_sync() -> None:
    """Force a full re-index on next allow_all asset list (e.g. after admin toggle)."""
    global _last_global_asset_sync, _last_output_index_sync
    _last_global_asset_sync = 0.0
    _last_output_index_sync = 0.0


def _sync_global_assets_if_needed() -> None:
    """Index all users' on-disk output/input when visibility is allow_all."""
    global _last_global_asset_sync
    now = time.time()
    if now - _last_global_asset_sync < GLOBAL_ASSET_SYNC_INTERVAL_SEC:
        return
    _last_global_asset_sync = now

    out_n = _sync_tree_into_assets(_global_output_root())
    in_n = _sync_tree_into_assets(_global_input_root())
    if out_n or in_n:
        _log.info(
            "Global asset index: %s output + %s input file(s) under %s",
            out_n,
            in_n,
            _global_output_root(),
        )


def _path_under_global_output(abs_path: str | None) -> bool:
    if not abs_path:
        return False
    root = os.path.normcase(os.path.abspath(_global_output_root()))
    norm = os.path.normcase(os.path.abspath(abs_path))
    return norm == root or norm.startswith(root + os.sep)


def _tags_for_output_file(abs_path: str) -> list[str]:
    """Derive asset tags for a file under global output/ (Generated tab needs 'output')."""
    locator = os.path.abspath(abs_path)
    try:
        from app.assets.services.path_utils import get_name_and_tags_from_asset_path

        _name, tags = get_name_and_tags_from_asset_path(locator)
        if tags:
            return tags
    except (ImportError, ValueError):
        pass
    root = _global_output_root()
    try:
        rel = os.path.relpath(locator, root).replace("\\", "/")
    except ValueError:
        rel = os.path.basename(locator)
    parts = [
        p
        for p in rel.split("/")[:-1]
        if p and p not in (".", "..") and p not in _SKIP_ASSET_DIR_NAMES
    ]
    return list(dict.fromkeys(["output", *parts]))


def _refresh_asset_tags_from_path(abs_path: str) -> bool:
    """Ensure DB tags match global path classification (required for Generated tab)."""
    locator = os.path.abspath(abs_path)
    if not os.path.isfile(locator):
        return False
    try:
        from app.database.db import create_session
        from app.assets.database.queries import ensure_tags_exist, set_reference_tags
    except ImportError:
        return False

    tags = _tags_for_output_file(locator) if _path_under_global_output(locator) else []
    if not tags:
        try:
            from app.assets.services.path_utils import get_name_and_tags_from_asset_path

            _name, tags = get_name_and_tags_from_asset_path(locator)
        except (ImportError, ValueError):
            return False
    if not tags:
        return False

    try:
        with create_session() as session:
            ref = _get_reference_by_path(session, locator)
            if ref is None:
                return False
            ensure_tags_exist(session, tags)
            set_reference_tags(
                session,
                reference_id=ref.id,
                tags=tags,
                origin="automatic",
            )
            session.commit()
            return True
    except Exception as e:
        _log.debug("refresh asset tags %s: %s", locator, e)
        return False


def _claim_output_asset_owner(abs_path: str, owner_id: str) -> None:
    """Assign owner_id on existing DB rows (seeder often leaves owner_id='')."""
    if not owner_id:
        return
    root = _global_output_root()
    if not _output_file_visible_to_user(abs_path, owner_id, root):
        return
    try:
        from app.database.db import create_session
    except ImportError:
        return

    locator = os.path.abspath(abs_path)
    try:
        with create_session() as session:
            ref = _get_reference_by_path(session, locator)
            if ref is None or ref.owner_id == owner_id:
                return
            ref.owner_id = owner_id
            session.commit()
    except Exception as e:
        _log.debug("claim output owner %s: %s", locator, e)


def _ingest_output_image(full: str, owner: str, user_id: str) -> None:
    _force_register_output_file(full, owner_id=owner, user_id=user_id)


def _output_file_visible_to_user(full_path: str, user_id: str, root: str) -> bool:
    """Whether an on-disk output file should be indexed for this user."""
    inferred = _owner_id_from_storage_path(full_path, root)
    if inferred and inferred == user_id:
        return True
    if path_belongs_to_user(full_path, user_id):
        return True
    return False


def _walk_output_images(
    root: str,
    user_id: str,
    mode: str,
    *,
    max_files: int,
    roots_first: tuple[str, ...] = (),
) -> int:
    """Walk output/ (optionally prioritizing subdirs) and register images."""
    count = 0
    seen_dirs: set[str] = set()

    def _walk_one(base: str) -> bool:
        nonlocal count
        if not base or not os.path.isdir(base):
            return False
        norm_base = os.path.normcase(os.path.abspath(base))
        if norm_base in seen_dirs:
            return False
        seen_dirs.add(norm_base)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [
                d
                for d in dirnames
                if d not in _SKIP_ASSET_DIR_NAMES and not d.startswith("_")
            ]
            for name in filenames:
                if os.path.splitext(name)[1].lower() not in _IMAGE_EXT:
                    continue
                full = os.path.join(dirpath, name)
                if mode == ASSETS_VISIBILITY_USER_SPECIFIC:
                    if not _output_file_visible_to_user(full, user_id, root):
                        continue
                    owner = user_id
                else:
                    owner = _owner_id_from_storage_path(full, root) or user_id
                try:
                    _ingest_output_image(full, owner, user_id)
                    count += 1
                except Exception as e:
                    _log.debug("ingest output %s: %s", full, e)
                if count >= max_files:
                    return True
        return False

    for sub in roots_first:
        if _walk_one(sub):
            return count
    if _walk_one(root):
        return count
    return count


def _sync_user_output_assets(user_id: str, max_files: int = 2500) -> int:
    """
    Register images under the global ComfyUI output/ tree for the Generated tab.

    Uses global output root (not per-user folder_paths chroot) so root-level
    files like output/ComfyUI_00001_.png and output/<user_id>/* are indexed.
    """
    if not user_id:
        return 0
    try:
        from app.assets.services.ingest import ingest_existing_file  # noqa: F401
    except ImportError:
        return 0

    root = _global_output_root()
    if not os.path.isdir(root):
        return 0

    mode = get_assets_imports_visibility()
    priority: tuple[str, ...] = ()
    if mode == ASSETS_VISIBILITY_USER_SPECIFIC:
        user_sub = os.path.join(root, user_id)
        if os.path.isdir(user_sub):
            priority = (user_sub,)

    count = _walk_output_images(
        root, user_id, mode, max_files=max_files, roots_first=priority
    )
    if count:
        _log.info(
            "Indexed %s output asset(s) for user %s under %s",
            count,
            user_id,
            root,
        )
    return count


def _sync_allow_all_output(*, force: bool = False, user_id: str | None = None) -> None:
    """Index entire output/ tree + repair tags so Generated shows all historical images."""
    global _last_output_index_sync, _last_global_asset_sync
    now = time.time()
    if not force and now - _last_output_index_sync < OUTPUT_INDEX_INTERVAL_SEC:
        return
    _last_output_index_sync = now
    _last_global_asset_sync = now

    _repair_output_asset_registry(user_id=user_id)


def _sync_output_index_if_needed(owner_id: str | None, *, force: bool = False) -> None:
    """Throttled: ensure output/ files are in the assets DB (Generated tab)."""
    global _last_output_index_sync
    now = time.time()
    if not force and now - _last_output_index_sync < OUTPUT_INDEX_INTERVAL_SEC:
        return
    _last_output_index_sync = now

    mode = get_assets_imports_visibility()
    if mode == ASSETS_VISIBILITY_DISABLE_ALL:
        return
    if mode == ASSETS_VISIBILITY_ALLOW_ALL:
        _sync_allow_all_output(force=force, user_id=owner_id)
    elif owner_id:
        if force:
            _repair_output_asset_registry(user_id=owner_id)
        else:
            _sync_user_output_assets(owner_id)


def sync_user_to_comfy_manager(user_id: str, username: str) -> None:
    """Ensure ComfyUI's users.json knows about this Usgromana user."""
    if not user_id:
        return

    manager = _get_user_manager()
    if manager is None:
        return

    try:
        if user_id not in manager.users:
            manager.users[user_id] = username or user_id
            users_file = manager.get_users_file()
            os.makedirs(os.path.dirname(users_file), exist_ok=True)
            with open(users_file, "w", encoding="utf-8") as f:
                json.dump(manager.users, f)
            _log.info("Registered ComfyUI user %s (%s)", user_id, username)
    except Exception as e:
        _log.warning("Failed to sync ComfyUI user %s: %s", user_id, e)


def _wrap_ingest_with_owner_id(func: Callable) -> Callable:
    def wrapper(*args, owner_id: str = "", **kwargs):
        if not owner_id:
            owner_id = access_control.get_current_user_id() or ""
        result = func(*args, owner_id=owner_id, **kwargs)
        if args:
            path = args[0]
            if isinstance(path, str) and os.path.isfile(path):
                _refresh_asset_tags_from_path(path)
        return result

    return wrapper


def _patch_user_manager_get_request_user_id() -> None:
    manager = _get_user_manager()
    if manager is None:
        return

    if getattr(manager, "_usgromana_get_user_patched", False):
        return

    original = manager.get_request_user_id

    def get_request_user_id(self, request):
        uid = get_comfy_user_id_for_request(request)
        if uid:
            try:
                if uid in self.users or uid == "default":
                    return uid
                return uid
            except Exception:
                return uid
        return original(request)

    import types

    manager.get_request_user_id = types.MethodType(get_request_user_id, manager)
    manager._usgromana_get_user_patched = True
    _log.info("Patched UserManager.get_request_user_id for Usgromana")


def _patch_comfy_users_list_route() -> None:
    """
    Prevent ComfyUI's 'Select a user' startup screen.

    When ``args.multi_user`` is true, GET /users returns a user list and the
    frontend shows a second login. Usgromana already authenticates via JWT.
    """
    try:
        from server import PromptServer
    except ImportError:
        return

    app = PromptServer.instance.app
    if getattr(app, "_usgromana_users_route_patched", False):
        return

    @web.middleware
    async def hide_comfy_user_picker(request, handler):
        if request.method == "GET" and request.path.rstrip("/") == "/users":
            return web.json_response({"storage": "server", "migrated": True})
        return await handler(request)

    # Outer middleware runs first on incoming requests.
    app.middlewares.insert(0, hide_comfy_user_picker)
    app._usgromana_users_route_patched = True
    _log.info("Hiding ComfyUI built-in user picker (Usgromana owns authentication)")


def _bind_asset_api_handlers(
    list_fn: Callable,
    detail_fn: Callable,
    resolve_fn: Callable,
) -> None:
    """
    Re-bind handlers on every module that imported them by value.

    ComfyUI's ``app.assets.api.routes`` does ``from app.assets.services import
    list_assets_page`` at import time; patching only asset_management is not enough.
    """
    try:
        from app.assets.services import asset_management as am

        am.list_assets_page = list_fn
        am.get_asset_detail = detail_fn
        am.resolve_asset_for_download = resolve_fn
    except ImportError:
        pass
    try:
        import app.assets.services as services_pkg

        services_pkg.list_assets_page = list_fn
        services_pkg.get_asset_detail = detail_fn
        services_pkg.resolve_asset_for_download = resolve_fn
    except ImportError:
        pass
    try:
        import app.assets.api.routes as routes_mod

        routes_mod.list_assets_page = list_fn
        routes_mod.get_asset_detail = detail_fn
        routes_mod.resolve_asset_for_download = resolve_fn
    except ImportError:
        pass


def _patch_asset_listing() -> None:
    try:
        from app.assets.services import asset_management as am
    except ImportError:
        _log.debug("ComfyUI assets module not available; skipping asset list patch")
        return

    if getattr(am, "_usgromana_list_patched", False):
        _bind_asset_api_handlers(
            am.list_assets_page,
            am.get_asset_detail,
            am.resolve_asset_for_download,
        )
        return

    original_list = am.list_assets_page
    original_detail = am.get_asset_detail
    original_resolve = am.resolve_asset_for_download

    def _filter_items(items, owner_id: str):
        if not owner_id:
            return []
        return [item for item in items if _item_visible_to_user(item, owner_id)]

    def _visibility_mode() -> str:
        return get_assets_imports_visibility()

    def _list_owner_for_query(mode: str, owner_id: str) -> str:
        """
        ComfyUI visibility: owner_id='' rows are shared seeds; owner_id=<user> are ingested runs.
        build_visible_owner_clause(user) returns both '' and user rows — required for listing.
        """
        if mode == ASSETS_VISIBILITY_DISABLE_ALL:
            return owner_id or ""
        return owner_id or ""

    def _list_with_all_owners(**kwargs):
        with _all_owners_visible():
            return original_list(owner_id="", **kwargs)

    def _apply_nsfw_to_list_result(result, *, context: str = ""):
        """NSFW-only pass; assets visibility is already applied."""
        if not is_nsfw_filter_active():
            return result
        before = len(result.items)
        filtered = filter_nsfw_asset_items(result.items)
        if before and not filtered:
            print(
                f"[Usgromana::Assets] All {before} asset(s) hidden by SFW/NSFW filter"
                f"{f' ({context})' if context else ''}"
            )
        return am.ListAssetsResult(
            items=filtered,
            total=len(filtered) if filtered else (0 if before else result.total),
        )

    def list_assets_page(owner_id: str = "", **kwargs):
        mode = _visibility_mode()
        if mode == ASSETS_VISIBILITY_DISABLE_ALL:
            return am.ListAssetsResult(items=[], total=0)

        kwargs = _list_kwargs_for_generated(kwargs)
        include_tags = kwargs.get("include_tags") or []
        tag_list = [
            (t.lower() if isinstance(t, str) else str(t).lower())
            for t in include_tags
        ]
        wants_output = "output" in tag_list

        if mode == ASSETS_VISIBILITY_ALLOW_ALL:
            if wants_output:
                _sync_allow_all_output(force=True, user_id=owner_id)
            else:
                _sync_global_assets_if_needed()
        else:
            _sync_output_index_if_needed(owner_id, force=wants_output)
        if mode == ASSETS_VISIBILITY_USER_SPECIFIC and owner_id:
            _sync_user_input_assets(owner_id)

        query_owner = _list_owner_for_query(mode, owner_id)

        if mode == ASSETS_VISIBILITY_ALLOW_ALL:
            result = _list_with_all_owners(**kwargs)
            filtered = _apply_nsfw_to_list_result(result, context="allow_all")
            if wants_output:
                print(
                    f"[Usgromana::Assets] Generated list: sql_total={result.total} "
                    f"returned={len(filtered.items)} (excludes _thumbs)"
                )
                if result.total and not filtered.items:
                    print(
                        "[Usgromana::Assets] Generated list empty after filters "
                        f"(mode={mode}, user={owner_id or 'n/a'})"
                    )
            return filtered

        result = original_list(owner_id=query_owner, **kwargs)

        if not SEPARATE_USERS or not owner_id:
            return _apply_nsfw_to_list_result(result, context="shared")

        filtered = _filter_items(result.items, owner_id)
        if len(filtered) == len(result.items):
            result = am.ListAssetsResult(items=filtered, total=result.total)
            return _apply_nsfw_to_list_result(result, context="user_specific")

        # Mixed page: fetch extra rows so path-filtered results are not empty after owner_id='' noise.
        limit = int(kwargs.get("limit") or 20)
        offset = int(kwargs.get("offset") or 0)
        if limit > 0 and len(filtered) < limit:
            wide = original_list(
                owner_id=query_owner,
                **{**kwargs, "limit": min(limit * 8, 500), "offset": offset},
            )
            filtered = _filter_items(wide.items, owner_id)[:limit]
        result = am.ListAssetsResult(items=filtered, total=max(len(filtered), result.total))
        filtered = _apply_nsfw_to_list_result(result, context="user_specific_wide")
        if wants_output and owner_id and not filtered.items:
            _log.info(
                "Assets list (user_specific, output): 0 items for user %s "
                "(sql=%s, after visibility=%s); indexing output/",
                owner_id,
                len(result.items),
                len(filtered.items),
            )
        return filtered

    def get_asset_detail(reference_id: str, owner_id: str = ""):
        mode = _visibility_mode()
        if mode == ASSETS_VISIBILITY_DISABLE_ALL:
            return None
        if mode == ASSETS_VISIBILITY_ALLOW_ALL:
            with _all_owners_visible():
                detail = original_detail(reference_id=reference_id, owner_id="")
                if asset_detail_is_nsfw_blocked(detail):
                    return None
                return detail
        query_owner = _list_owner_for_query(mode, owner_id)
        detail = original_detail(reference_id=reference_id, owner_id=query_owner)
        if (
            detail
            and mode == ASSETS_VISIBILITY_USER_SPECIFIC
            and SEPARATE_USERS
            and owner_id
            and not _detail_visible_to_user(detail, owner_id)
        ):
            return None
        if asset_detail_is_nsfw_blocked(detail):
            return None
        return detail

    def resolve_asset_for_download(reference_id: str, owner_id: str = ""):
        mode = _visibility_mode()
        if mode == ASSETS_VISIBILITY_DISABLE_ALL:
            raise ValueError("Asset not found")
        if mode == ASSETS_VISIBILITY_ALLOW_ALL:
            with _all_owners_visible():
                result = original_resolve(reference_id=reference_id, owner_id="")
                if asset_download_is_nsfw_blocked(result):
                    raise ValueError("Asset not found")
                return result
        query_owner = _list_owner_for_query(mode, owner_id)
        detail = original_detail(reference_id=reference_id, owner_id=query_owner)
        if (
            detail
            and mode == ASSETS_VISIBILITY_USER_SPECIFIC
            and SEPARATE_USERS
            and owner_id
            and not _detail_visible_to_user(detail, owner_id)
        ):
            raise ValueError("Asset not found")
        if asset_detail_is_nsfw_blocked(detail):
            raise ValueError("Asset not found")
        result = original_resolve(reference_id=reference_id, owner_id=query_owner)
        if asset_download_is_nsfw_blocked(result):
            raise ValueError("Asset not found")
        return result

    _bind_asset_api_handlers(
        list_assets_page, get_asset_detail, resolve_asset_for_download
    )
    am._usgromana_list_patched = True
    _log.info(
        "Patched ComfyUI asset listing (visibility + routes rebind + NSFW filter)"
    )


def _patch_asset_scanner_prefixes() -> None:
    """Asset seeder must scan/collect from global input/output roots."""
    try:
        from app.assets import scanner as asset_scanner
        from app.assets.services.file_utils import list_files_recursively
    except ImportError:
        return

    if getattr(asset_scanner, "_usgromana_prefix_patched", False):
        return

    original_prefixes = asset_scanner.get_prefixes_for_root
    original_collect = asset_scanner.collect_paths_for_roots

    def get_prefixes_for_root(root):
        if root == "output":
            return [os.path.abspath(_global_output_root())]
        if root == "input":
            return [os.path.abspath(_global_input_root())]
        return original_prefixes(root)

    def collect_paths_for_roots(roots):
        paths: list[str] = []
        if "models" in roots:
            paths.extend(asset_scanner.collect_models_files())
        if "input" in roots:
            paths.extend(list_files_recursively(_global_input_root()))
        if "output" in roots:
            paths.extend(list_files_recursively(_global_output_root()))
        return paths

    asset_scanner.get_prefixes_for_root = get_prefixes_for_root
    asset_scanner.collect_paths_for_roots = collect_paths_for_roots
    asset_scanner._usgromana_prefix_patched = True
    _patch_asset_scanner_build_specs()
    _log.info(
        "Patched asset scanner (collect + prefixes, global output=%s)",
        _global_output_root(),
    )


def _patch_asset_scanner_build_specs() -> None:
    """When the seeder skips existing paths, still repair output tags and is_missing."""
    try:
        import app.assets.scanner as sc
    except ImportError:
        return

    if getattr(sc, "_usgromana_build_specs_patched", False):
        return

    original = sc.build_asset_specs

    def build_asset_specs(paths, existing_paths, *args, **kwargs):
        for p in paths:
            abs_p = os.path.abspath(p)
            if abs_p not in existing_paths:
                continue
            if _is_thumb_asset_path(abs_p) or not _path_under_global_output(abs_p):
                continue
            _clear_missing_flag_for_path(abs_p)
            _refresh_asset_tags_from_path(abs_p)
        return original(paths, existing_paths, *args, **kwargs)

    sc.build_asset_specs = build_asset_specs
    sc._usgromana_build_specs_patched = True
    _log.info("Patched asset scanner build_asset_specs (repair skipped output paths)")


def _patch_asset_path_utils() -> None:
    """Classify asset paths against global input/output roots so previews resolve."""
    try:
        from app.assets.services import path_utils as pu
    except ImportError:
        return

    if getattr(pu, "_usgromana_path_patched", False):
        return

    original = pu.get_asset_category_and_relative_path

    def classify_with_global_roots(file_path: str):
        saved_out = folder_paths.get_output_directory
        saved_in = folder_paths.get_input_directory
        saved_tmp = folder_paths.get_temp_directory
        folder_paths.get_output_directory = access_control._AccessControl__get_output_directory
        folder_paths.get_input_directory = access_control._AccessControl__get_input_directory
        folder_paths.get_temp_directory = access_control._AccessControl__get_temp_directory
        try:
            return original(file_path)
        finally:
            folder_paths.get_output_directory = saved_out
            folder_paths.get_input_directory = saved_in
            folder_paths.get_temp_directory = saved_tmp

    pu.get_asset_category_and_relative_path = classify_with_global_roots
    pu._usgromana_path_patched = True
    _log.info("Patched ComfyUI asset path utils for global output/input roots")


def _patch_asset_ingest() -> None:
    try:
        from app.assets.services import ingest as ingest_mod
    except ImportError:
        return

    if getattr(ingest_mod, "_usgromana_ingest_patched", False):
        return

    for name in (
        "register_file_in_place",
        "ingest_existing_file",
        "upload_from_temp_path",
        "_ingest_file_from_path",
    ):
        if hasattr(ingest_mod, name):
            setattr(ingest_mod, name, _wrap_ingest_with_owner_id(getattr(ingest_mod, name)))

    ingest_mod._usgromana_ingest_patched = True
    _log.info("Patched ComfyUI asset ingest to assign owner_id from JWT user")


def install_comfy_user_bridge() -> None:
    """Install all ComfyUI ↔ Usgromana user bridges (idempotent, retriable)."""
    global _user_manager_patched
    if not SEPARATE_USERS:
        return

    if not _user_manager_patched:
        _patch_user_manager_get_request_user_id()
        _user_manager_patched = getattr(
            _get_user_manager(), "_usgromana_get_user_patched", False
        )

    _patch_asset_scanner_prefixes()
    _patch_asset_path_utils()
    _patch_asset_listing()
    _patch_asset_ingest()
    _patch_comfy_users_list_route()


def _preview_output_key(preview: dict | None) -> tuple[str, str] | None:
    if not preview or not isinstance(preview, dict):
        return None
    filename = (preview.get("filename") or "").strip()
    if not filename:
        return None
    subfolder = (preview.get("subfolder") or "").replace("\\", "/").strip("/")
    return (subfolder, filename)


def _filename_parts_from_asset_meta(meta: dict | None, fallback_name: str | None) -> tuple[str, str]:
    raw = (meta or {}).get("filename") or fallback_name or ""
    raw = str(raw).replace("\\", "/")
    if "/" in raw:
        subfolder, filename = raw.rsplit("/", 1)
        return subfolder, filename
    return "", raw


def _created_at_epoch_ms(ref) -> int:
    created = getattr(ref, "created_at", None)
    if created is None:
        return int(time.time() * 1000)
    if isinstance(created, (int, float)):
        value = int(created)
        return value if value > 1_000_000_000_000 else value * 1000
    try:
        return int(created.timestamp() * 1000)
    except Exception:
        return int(time.time() * 1000)


def _asset_summary_to_completed_job(item) -> dict | None:
    """Build a /api/jobs row so Comfy's Generated tab can render a disk-backed image."""
    ref = getattr(item, "ref", None)
    if ref is None:
        return None
    subfolder, filename = _filename_parts_from_asset_meta(
        getattr(ref, "user_metadata", None) or {},
        getattr(ref, "name", None),
    )
    if not filename:
        return None
    ref_id = getattr(ref, "id", None) or filename
    return {
        "id": f"usgromana-asset-{ref_id}",
        "status": "completed",
        "create_time": _created_at_epoch_ms(ref),
        "outputs_count": 1,
        "preview_output": {
            "filename": filename,
            "subfolder": subfolder,
            "type": "output",
            "nodeId": "0",
            "mediaType": "images",
        },
    }


def _list_generated_asset_items(owner_id: str | None, *, limit: int = 500) -> list:
    """Output-tagged asset rows from the DB (same source as /api/assets Generated)."""
    try:
        from app.assets.services import asset_management as am
    except ImportError:
        return []

    if not getattr(am, "_usgromana_list_patched", False):
        _patch_asset_listing()

    mode = get_assets_imports_visibility()
    if mode == ASSETS_VISIBILITY_DISABLE_ALL:
        return []

    kwargs = {
        "include_tags": ["output"],
        "exclude_tags": list(_GENERATED_EXCLUDE_TAGS),
        "limit": limit,
        "offset": 0,
        "sort": "created_at",
        "order": "desc",
    }

    if mode == ASSETS_VISIBILITY_ALLOW_ALL:
        with _all_owners_visible():
            result = am.list_assets_page(owner_id="", **kwargs)
    else:
        query_owner = owner_id or ""
        result = am.list_assets_page(owner_id=query_owner, **kwargs)
        if SEPARATE_USERS and owner_id:
            filtered = [
                item
                for item in result.items
                if _item_visible_to_user(item, owner_id)
            ]
            result = am.ListAssetsResult(items=filtered, total=len(filtered))

    if not is_nsfw_filter_active():
        return list(result.items)

    filtered = filter_nsfw_asset_items(result.items)
    return list(filtered)


def _merge_disk_outputs_into_jobs_payload(
    payload: dict,
    *,
    owner_id: str | None,
    offset: int,
    limit: int | None,
) -> dict:
    """
    Comfy's Generated tab lists /api/jobs (history), not /api/assets.
    Inject completed jobs built from indexed output/ files on the first page.
    """
    if offset > 0:
        return payload

    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return payload

    existing_keys: set[tuple[str, str]] = set()
    for job in jobs:
        if not isinstance(job, dict) or job.get("status") != "completed":
            continue
        key = _preview_output_key(job.get("preview_output"))
        if key:
            existing_keys.add(key)

    synthetic: list[dict] = []
    for item in _list_generated_asset_items(owner_id, limit=500):
        job = _asset_summary_to_completed_job(item)
        if not job:
            continue
        key = _preview_output_key(job.get("preview_output"))
        if key and key in existing_keys:
            continue
        if key:
            existing_keys.add(key)
        synthetic.append(job)

    if not synthetic:
        return payload

    merged = [j for j in jobs if isinstance(j, dict)] + synthetic
    merged.sort(key=lambda j: int(j.get("create_time") or 0), reverse=True)

    page_limit = limit if limit and limit > 0 else len(merged)
    page_jobs = merged[:page_limit]

    pagination = dict(payload.get("pagination") or {})
    pagination["total"] = int(pagination.get("total") or 0) + len(synthetic)
    pagination["has_more"] = bool(pagination.get("has_more")) or len(merged) > page_limit
    if limit is not None:
        pagination["limit"] = limit
    pagination["offset"] = offset

    print(
        f"[Usgromana::Assets] Generated tab: merged {len(synthetic)} disk image(s) "
        f"into /api/jobs (page size {len(page_jobs)})"
    )
    return {**payload, "jobs": page_jobs, "pagination": pagination}


def _request_wants_generated_assets(request: web.Request) -> bool:
    """True when the client is listing the Generated (output) assets tab."""
    if request.method != "GET":
        return False
    raw = request.rel_url.query.getall("include_tags", [])
    tags: list[str] = []
    for item in raw:
        if isinstance(item, str):
            tags.extend(t.strip().lower() for t in item.split(",") if t.strip())
    single = request.rel_url.query.get("include_tags")
    if isinstance(single, str):
        tags.extend(t.strip().lower() for t in single.split(",") if t.strip())
    return "output" in tags


def create_comfy_user_middleware():
    """Middleware: sync JWT user into ComfyUI user manager."""

    @web.middleware
    async def middleware(request: web.Request, handler):
        install_comfy_user_bridge()

        user_id = get_comfy_user_id_for_request(request)
        username = request.get("user") if isinstance(request.get("user"), str) else None

        if user_id:
            sync_user_to_comfy_manager(user_id, username or user_id)
            access_control.set_current_user_id(user_id, set_fallback=True)

        if username:
            try:
                from ..globals import current_username_var

                current_username_var.set(username)
            except Exception:
                pass

        path = request.path or ""
        if request.method == "GET" and path.rstrip("/") == "/api/assets":
            try:
                from app.assets.services import asset_management as am

                if getattr(am, "_usgromana_list_patched", False):
                    _bind_asset_api_handlers(
                        am.list_assets_page,
                        am.get_asset_detail,
                        am.resolve_asset_for_download,
                    )
            except ImportError:
                pass

        assets_mode = get_assets_imports_visibility()
        if (
            request.method == "GET"
            and path.rstrip("/") == "/api/assets"
            and _request_wants_generated_assets(request)
            and assets_mode != ASSETS_VISIBILITY_DISABLE_ALL
        ):
            global _thumb_purge_done
            if not _thumb_purge_done:
                _thumb_purge_done = True
                _purge_thumb_asset_references()
            if assets_mode == ASSETS_VISIBILITY_ALLOW_ALL:
                _sync_allow_all_output(force=True, user_id=user_id)
            elif user_id:
                _repair_output_asset_registry(user_id=user_id)

        if (
            assets_mode == ASSETS_VISIBILITY_DISABLE_ALL
            and request.method == "GET"
            and path.rstrip("/") == "/api/assets"
        ):
            return web.json_response(
                {"assets": [], "total": 0, "has_more": False},
                status=200,
            )

        if path.startswith("/usgromana-gallery"):
            mode = assets_mode
            if (
                mode == ASSETS_VISIBILITY_DISABLE_ALL
                and path.rstrip("/").endswith("/list")
                and request.method == "GET"
            ):
                return web.json_response(
                    {"ok": True, "images": [], "folders": []},
                    status=200,
                )
            with gallery_scan_folder_paths(mode, user_id):
                return await handler(request)

        if (
            request.method == "GET"
            and path.rstrip("/") == "/api/jobs"
            and assets_mode != ASSETS_VISIBILITY_DISABLE_ALL
        ):
            status_param = (request.rel_url.query.get("status") or "").lower()
            if "completed" in status_param:
                if assets_mode == ASSETS_VISIBILITY_ALLOW_ALL:
                    _sync_allow_all_output(force=False, user_id=user_id)
                elif user_id:
                    _sync_output_index_if_needed(user_id, force=False)

        response = await handler(request)

        if (
            request.method == "GET"
            and path.rstrip("/") == "/api/jobs"
            and assets_mode != ASSETS_VISIBILITY_DISABLE_ALL
        ):
            status_param = (request.rel_url.query.get("status") or "").lower()
            if "completed" in status_param:
                try:
                    offset = int(request.rel_url.query.get("offset") or 0)
                except (TypeError, ValueError):
                    offset = 0
                limit_raw = request.rel_url.query.get("limit")
                limit = None
                if limit_raw is not None:
                    try:
                        limit = int(limit_raw)
                    except (TypeError, ValueError):
                        limit = None

                content_type = response.content_type or ""
                body = getattr(response, "body", None)
                if response.status == 200 and body and "json" in content_type:
                    payload = json.loads(body)
                    merged = _merge_disk_outputs_into_jobs_payload(
                        payload,
                        owner_id=user_id,
                        offset=max(0, offset),
                        limit=limit,
                    )
                    return web.json_response(merged, status=200)

        return response

    return middleware

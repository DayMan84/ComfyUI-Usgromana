"""Per-image gallery shares between Usgromana accounts.

Images stay in the owner's output folder. A share record grants other
accounts permission to see that file in the gallery. Owners can revoke
those grants and list who currently has visibility.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from typing import Iterable

_LOCK = threading.Lock()
_USER_ID_RE_LEN = 36


def normalize_relpath(relpath: str | None) -> str | None:
    """Return a safe relative path, or None when it could escape the owner folder."""
    if not isinstance(relpath, str):
        return None
    clean = relpath.replace("\\", "/").strip()
    if not clean or clean.startswith("shared/"):
        return None
    parts = [part for part in clean.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return None
    return "/".join(parts)


def parse_shared_relpath(relpath: str | None) -> tuple[str, str] | None:
    """Parse ``shared/<owner_id>/<relpath>`` into owner id and inner relative path."""
    if not isinstance(relpath, str):
        return None
    clean = relpath.replace("\\", "/").strip().lstrip("/")
    prefix = "shared/"
    if not clean.startswith(prefix):
        return None
    rest = clean[len(prefix) :]
    owner_id, sep, inner = rest.partition("/")
    if not sep or not _valid_user_id(owner_id):
        return None
    normalized = normalize_relpath(inner)
    if not normalized:
        return None
    return owner_id, normalized


def shared_relpath(owner_id: str, relpath: str) -> str:
    return f"shared/{owner_id}/{relpath}"


def _valid_user_id(user_id: str) -> bool:
    if not isinstance(user_id, str) or len(user_id) != _USER_ID_RE_LEN:
        return False
    try:
        uuid.UUID(user_id)
    except ValueError:
        return False
    return True


class ImageShareStore:
    """JSON-backed grants of gallery images from an owner to other usernames."""

    def __init__(self, store_path: str, output_root: str):
        self.store_path = store_path
        self.output_root = os.path.abspath(output_root)

    def owner_output_dir(self, owner_id: str) -> str:
        return os.path.abspath(os.path.join(self.output_root, owner_id))

    def resolve_owned_file(self, owner_id: str, relpath: str | None) -> str | None:
        normalized = normalize_relpath(relpath)
        if not normalized or not _valid_user_id(owner_id):
            return None
        root = os.path.realpath(self.owner_output_dir(owner_id))
        joined = os.path.join(root, *normalized.split("/"))
        if not os.path.isfile(joined):
            return None
        # realpath follows symlinks so a link inside the owner folder cannot
        # point at another account's file.
        candidate = os.path.realpath(joined)
        if os.path.normcase(candidate) != os.path.normcase(root) and not os.path.normcase(
            candidate
        ).startswith(os.path.normcase(root) + os.sep):
            return None
        return candidate

    def share(self, owner_id: str, relpaths: Iterable[str], usernames: Iterable[str], known_users: set[str]) -> dict:
        """Grant usernames visibility of the owner's images. Unknown users are rejected."""
        viewers = _clean_usernames(usernames)
        unknown = sorted(name for name in viewers if name not in known_users)
        if unknown:
            raise ValueError("Unknown account: " + ", ".join(unknown))
        paths = _clean_paths(relpaths)
        if not paths or not viewers:
            raise ValueError("Choose at least one image and one account")
        missing = [rel for rel in paths if self.resolve_owned_file(owner_id, rel) is None]
        if missing:
            raise ValueError("Image not found: " + ", ".join(missing))

        with _LOCK:
            data = self._load()
            for rel in paths:
                entry = _entry_for(data, owner_id, rel)
                current = set(entry["viewers"])
                current.update(viewers)
                entry["viewers"] = sorted(current)
            self._save(data)
        return {"shares": self.visibility(owner_id, paths)}

    def revoke(self, owner_id: str, relpaths: Iterable[str], usernames: Iterable[str]) -> dict:
        """Remove grants. The owner always keeps their own visibility."""
        viewers = _clean_usernames(usernames)
        paths = _clean_paths(relpaths)
        if not paths or not viewers:
            raise ValueError("Choose at least one image and one account")
        with _LOCK:
            data = self._load()
            for rel in paths:
                entry = _find_entry(data, owner_id, rel)
                if entry is None:
                    continue
                entry["viewers"] = [name for name in entry["viewers"] if name not in viewers]
                if not entry["viewers"]:
                    data["shares"] = [
                        item for item in data["shares"] if not _same_image(item, owner_id, rel)
                    ]
            self._save(data)
        return {"shares": self.visibility(owner_id, paths)}

    def visibility(self, owner_id: str, relpaths: Iterable[str]) -> list[dict]:
        """Who can see each owned image: the owner plus current grantees."""
        paths = _clean_paths(relpaths)
        data = self._load()
        result = []
        for rel in paths:
            entry = _find_entry(data, owner_id, rel)
            viewers = list(entry["viewers"]) if entry else []
            result.append({"relpath": rel, "viewers": viewers})
        return result

    def shares_for_viewer(self, viewer_username: str) -> list[dict]:
        """Images other accounts have shared with this username."""
        if not viewer_username:
            return []
        data = self._load()
        visible = []
        for entry in data.get("shares", []):
            if viewer_username not in entry.get("viewers", []):
                continue
            owner_id = entry.get("owner_id")
            relpath = entry.get("relpath")
            full = self.resolve_owned_file(owner_id, relpath)
            if not full:
                continue
            stat = os.stat(full)
            visible.append(
                {
                    "owner_id": owner_id,
                    "relpath": relpath,
                    "shared_relpath": shared_relpath(owner_id, relpath),
                    "filename": os.path.basename(relpath),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                    "path": full,
                }
            )
        return visible

    def can_view(self, viewer_user_id: str | None, viewer_username: str | None, owner_id: str, relpath: str) -> bool:
        if viewer_user_id and viewer_user_id == owner_id:
            return self.resolve_owned_file(owner_id, relpath) is not None
        if not viewer_username:
            return False
        normalized = normalize_relpath(relpath)
        if not normalized:
            return False
        for entry in self._load().get("shares", []):
            if (
                entry.get("owner_id") == owner_id
                and entry.get("relpath") == normalized
                and viewer_username in entry.get("viewers", [])
            ):
                return self.resolve_owned_file(owner_id, normalized) is not None
        return False

    def _load(self) -> dict:
        if not os.path.isfile(self.store_path):
            return {"shares": []}
        try:
            with open(self.store_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {"shares": []}
        if not isinstance(data, dict) or not isinstance(data.get("shares"), list):
            return {"shares": []}
        return data

    def _save(self, data: dict) -> None:
        parent = os.path.dirname(self.store_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        temporary = f"{self.store_path}.tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        os.replace(temporary, self.store_path)


def _clean_usernames(usernames: Iterable[str]) -> list[str]:
    cleaned = []
    seen = set()
    for name in usernames:
        if not isinstance(name, str):
            continue
        stripped = name.strip()
        if not stripped or stripped in seen or stripped.lower() == "guest":
            continue
        seen.add(stripped)
        cleaned.append(stripped)
    return cleaned


def _clean_paths(relpaths: Iterable[str]) -> list[str]:
    cleaned = []
    seen = set()
    for rel in relpaths:
        normalized = normalize_relpath(rel)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned


def _same_image(entry: dict, owner_id: str, relpath: str) -> bool:
    return entry.get("owner_id") == owner_id and entry.get("relpath") == relpath


def _find_entry(data: dict, owner_id: str, relpath: str) -> dict | None:
    for entry in data.get("shares", []):
        if _same_image(entry, owner_id, relpath):
            return entry
    return None


def _entry_for(data: dict, owner_id: str, relpath: str) -> dict:
    entry = _find_entry(data, owner_id, relpath)
    if entry is None:
        entry = {"owner_id": owner_id, "relpath": relpath, "viewers": []}
        data.setdefault("shares", []).append(entry)
    if not isinstance(entry.get("viewers"), list):
        entry["viewers"] = []
    return entry

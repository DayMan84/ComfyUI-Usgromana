"""Safe layout and path resolution for the live ``users/`` data directory.

Never deletes or recreates ``users/``. Only creates missing directories and empty
optional files. Picks an existing user database file when the configured path is
empty but a legacy file still has accounts.
"""
import os

from .json_utils import load_json_file

USERS_DIR_NAME = "users"
DEFAULTS_SUBDIR = "defaults"


def ensure_users_data_layout(base_dir: str, touch_files: list[str] | None = None) -> str:
    """
    Create ``users/`` and ``users/defaults/`` if missing. Touch list files only when absent.
    Returns the absolute users directory path.
    """
    users_dir = os.path.join(base_dir, USERS_DIR_NAME)
    defaults_dir = os.path.join(users_dir, DEFAULTS_SUBDIR)
    os.makedirs(defaults_dir, exist_ok=True)

    for path in touch_files or []:
        if not path:
            continue
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if not os.path.exists(path):
            try:
                with open(path, "a", encoding="utf-8"):
                    pass
            except OSError as e:
                print(f"[Usgromana] Could not create {path}: {e}")

    return users_dir


def _user_count(path: str) -> int:
    if not os.path.isfile(path):
        return 0
    data = load_json_file(path, {})
    return len(data) if isinstance(data, dict) else 0


def resolve_users_database_path(configured_path: str, base_dir: str) -> str:
    """
    Resolve which JSON file holds accounts. Prefer the path with the most users.
    Does not move or merge files automatically (avoids surprise writes on upgrade).
    """
    if os.path.isabs(configured_path):
        configured_abs = os.path.normpath(configured_path)
    else:
        configured_abs = os.path.normpath(os.path.join(base_dir, configured_path))

    users_dir = os.path.join(base_dir, USERS_DIR_NAME)
    candidates = [
        configured_abs,
        os.path.join(users_dir, "users.json"),
        os.path.join(users_dir, "users_db.json"),
    ]

    seen: set[str] = set()
    unique: list[str] = []
    for path in candidates:
        norm = os.path.normpath(path)
        if norm not in seen:
            seen.add(norm)
            unique.append(norm)

    best = configured_abs
    best_n = _user_count(configured_abs)
    for path in unique:
        n = _user_count(path)
        if n > best_n:
            best_n = n
            best = path

    if best != configured_abs and best_n > 0:
        print(
            f"[Usgromana] User database: using {best} ({best_n} account(s)). "
            f"Configured path {configured_abs} is empty or missing."
        )

    parent = os.path.dirname(best)
    if parent:
        os.makedirs(parent, exist_ok=True)

    return best

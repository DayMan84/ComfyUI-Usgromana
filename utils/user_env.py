"""
ComfyUI-usgromana per-user environment helpers.

Responsible for:
- Resolving the extension root
- Managing the shared Users/ directory
- Creating / locating per-user folders (Users/<username>/...)
- Loading / saving per-user settings JSON
- Centralizing paths for user_db.json and (renamed) usgromana_settings.js
"""

import os
import json
from typing import Any, Dict
import shutil
from typing import List

# -----------------------
# Path helpers
# -----------------------

def get_extension_root() -> str:
    """
    Returns the root directory of the ComfyUI-Usgromana extension.
    Assumes this file lives in `<root>/utils/user_env.py`.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, ".."))


def get_users_root() -> str:
    """
    Root folder for all Usgromana user-related files:
      <ext_root>/Users/
    """
    root = os.path.join(get_extension_root(), "Users")
    os.makedirs(root, exist_ok=True)
    return root


def get_user_db_path() -> str:
    """
    Global user database JSON.
      <ext_root>/Users/user_db.json
    """
    return os.path.join(get_users_root(), "user_db.json")


def get_frontend_settings_js_path() -> str:
    """
    Location of the frontend settings JS file (renamed from sentinel_settings.js):
      <ext_root>/Users/usgromana_settings.js

    This file is still served as a static asset by the backend, but physically
    lives under Users/ so everything related to Usgromana is in one place.
    """
    return os.path.join(get_users_root(), "usgromana_settings.js")


def get_user_root(username: str) -> str:
    """
    Per-user root folder:
      <ext_root>/Users/<username>/
    """
    username = (username or "guest").strip() or "guest"
    path = os.path.join(get_users_root(), username)
    os.makedirs(path, exist_ok=True)
    return path


def get_user_css_dir(username: str) -> str:
    """
    Per-user CSS directory:
      <ext_root>/Users/<username>/css/
    """
    path = os.path.join(get_user_root(username), "css")
    os.makedirs(path, exist_ok=True)
    return path


def get_user_settings_path(username: str) -> str:
    """
    Per-user settings JSON file:
      <ext_root>/Users/<username>/settings.json
    """
    return os.path.join(get_user_root(username), "settings.json")


# -----------------------
# JSON helpers
# -----------------------

def _load_json_file(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Don't explode the whole app if someone corrupts a file.
        return default


def _save_json_file(path: str, data: Any) -> None:
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


# -----------------------
# Per-user settings API
# -----------------------

def load_user_settings(username: str) -> Dict[str, Any]:
    """
    Load per-user settings JSON. Returns {} if missing or invalid.
    """
    path = get_user_settings_path(username)
    data = _load_json_file(path, {})
    return data if isinstance(data, dict) else {}


def save_user_settings(username: str, settings: Dict[str, Any]) -> None:
    """
    Save per-user settings JSON. Non-dicts are ignored.
    """
    if not isinstance(settings, dict):
        return
    path = get_user_settings_path(username)
    _save_json_file(path, settings)


# -----------------------
# Group / global config path helper (optional)
# -----------------------

def get_groups_config_path(filename: str = "usgromana_groups.json") -> str:
    """
    Path helper for the role/group config file.

    If you want to rename sentinel_groups.json to usgromana_groups.json and keep
    it in the extension root, this gives you a single place to reference it.
    """
    return os.path.join(get_extension_root(), filename)

def get_gallery_root_config_path() -> str:
    """
    Global config pointing at which user is used as Gallery root.

      <ext_root>/Users/gallery_root.json

    Stored as: { "user": "<username>" }
    """
    return os.path.join(get_users_root(), "gallery_root.json")


def get_gallery_root_user() -> str | None:
    """
    Return the username currently configured as Gallery root, or None.
    """
    data = _load_json_file(get_gallery_root_config_path(), {})
    user = data.get("user")
    if isinstance(user, str) and user.strip():
        return user.strip()
    return None


def set_gallery_root_user(username: str | None) -> None:
    """
    Set or clear the Gallery root user.
    If username is None or empty, the gallery root is cleared.
    """
    path = get_gallery_root_config_path()
    if not username:
        _save_json_file(path, {})
        return

    username = username.strip()
    if not username:
        _save_json_file(path, {})
        return

    _save_json_file(path, {"user": username})


def list_user_files(username: str, max_files: int = 500) -> List[str]:
    """
    Return a relative list of files under the user's root directory.

      Users/<username>/...

    Limited to max_files entries to avoid insane payloads.
    """
    root = get_user_root(username)
    collected: List[str] = []

    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            collected.append(rel)
            if len(collected) >= max_files:
                return collected
    return collected


def purge_user_root(username: str) -> None:
    """
    Delete the entire per-user folder under Users/<username>/ and recreate it.
    """
    root = get_user_root(username)
    if os.path.exists(root):
        shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root, exist_ok=True)

def get_user_workflow_dir(username: str) -> str:
    """
    Per-user workflow directory:
      <ext_root>/Users/<username>/workflows/
    """
    user_root = get_user_root(username)
    wf_dir = os.path.join(user_root, "workflows")
    os.makedirs(wf_dir, exist_ok=True)
    return wf_dir

def list_user_workflows(username: str) -> List[str]:
    """
    Returns a list of workflow filenames (relative paths) for the user.
    """
    wf_dir = get_user_workflow_dir(username)
    workflows = []
    if os.path.exists(wf_dir):
        for root, _, files in os.walk(wf_dir):
            for file in files:
                if file.endswith(".json"):
                    # We store them relative to the workflow folder
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, wf_dir)
                    workflows.append(rel_path)
    return workflows
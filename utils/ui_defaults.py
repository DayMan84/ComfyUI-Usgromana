"""Global UI default toggles (admin-configured, not per-role)."""

from ..constants import DEFAULT_UI_DEFAULTS_PATH, UI_DEFAULTS_FILE
from .json_utils import load_json_file, save_json_file

ASSETS_VISIBILITY_USER_SPECIFIC = "user_specific"
ASSETS_VISIBILITY_ALLOW_ALL = "allow_all"
ASSETS_VISIBILITY_DISABLE_ALL = "disable_all"

ASSETS_VISIBILITY_MODES = (
    ASSETS_VISIBILITY_USER_SPECIFIC,
    ASSETS_VISIBILITY_ALLOW_ALL,
    ASSETS_VISIBILITY_DISABLE_ALL,
)

_BUILTIN_DEFAULTS = {
    "assets_imports_visibility": ASSETS_VISIBILITY_USER_SPECIFIC,
}


def load_default_ui_defaults() -> dict:
    cfg = load_json_file(DEFAULT_UI_DEFAULTS_PATH, None)
    if not isinstance(cfg, dict):
        return dict(_BUILTIN_DEFAULTS)
    return {**_BUILTIN_DEFAULTS, **cfg}


def ensure_ui_defaults_config() -> None:
    """Create or merge missing keys into the live UI defaults file."""
    default_cfg = load_default_ui_defaults()
    current = load_json_file(UI_DEFAULTS_FILE, {})
    if not isinstance(current, dict):
        current = {}
    changed = False
    for key, value in default_cfg.items():
        if key not in current:
            current[key] = value
            changed = True
    if changed:
        save_json_file(UI_DEFAULTS_FILE, current)


def get_ui_defaults() -> dict:
    ensure_ui_defaults_config()
    default_cfg = load_default_ui_defaults()
    current = load_json_file(UI_DEFAULTS_FILE, {})
    if not isinstance(current, dict):
        return dict(default_cfg)
    merged = dict(default_cfg)
    merged.update(current)
    return merged


def get_assets_imports_visibility() -> str:
    mode = get_ui_defaults().get("assets_imports_visibility", ASSETS_VISIBILITY_USER_SPECIFIC)
    if mode not in ASSETS_VISIBILITY_MODES:
        return ASSETS_VISIBILITY_USER_SPECIFIC
    return mode


def set_assets_imports_visibility(mode: str) -> str:
    if mode not in ASSETS_VISIBILITY_MODES:
        raise ValueError(
            f"Invalid assets_imports_visibility: {mode!r}. "
            f"Expected one of: {', '.join(ASSETS_VISIBILITY_MODES)}"
        )
    ensure_ui_defaults_config()
    current = load_json_file(UI_DEFAULTS_FILE, {})
    if not isinstance(current, dict):
        current = {}
    current["assets_imports_visibility"] = mode
    save_json_file(UI_DEFAULTS_FILE, current)
    try:
        from .comfy_user_bridge import (
            reset_global_asset_sync,
            schedule_output_registry_repair,
        )

        reset_global_asset_sync()
        schedule_output_registry_repair()
    except Exception:
        pass
    return mode

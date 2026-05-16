"""
Enable ComfyUI's built-in assets system without requiring --enable-assets on the CLI.

ComfyUI checks ``args.enable_assets`` when constructing ``PromptServer`` (before custom
node ``__init__`` files run). Usgromana's ``prestartup_script.py`` calls this early;
``__init__.py`` calls it again as a safety net for the frontend feature flag.
"""

from __future__ import annotations

import logging

_log = logging.getLogger("usgromana.assets")
_applied = False


def enable_comfy_assets(*, log: bool = True) -> bool:
    """
    Turn on ComfyUI assets (API routes, DB seeder, frontend capability flag).
    Returns True if assets were enabled or were already enabled.
    """
    global _applied
    try:
        from comfy.cli_args import args
    except ImportError:
        return False

    already = bool(getattr(args, "enable_assets", False))
    if not already:
        args.enable_assets = True
        if log:
            _log.info(
                "[Usgromana] Enabled ComfyUI assets system "
                "(no --enable-assets startup flag required)."
            )

    try:
        from comfy_api import feature_flags

        if not feature_flags.SERVER_FEATURE_FLAGS.get("assets"):
            feature_flags.SERVER_FEATURE_FLAGS["assets"] = True
    except Exception as e:
        _log.debug("Could not update ComfyUI feature_flags.assets: %s", e)

    _applied = True
    return True


def assets_enable_requested() -> bool:
    """Whether Usgromana should auto-enable Comfy assets (config opt-out)."""
    try:
        from ..constants import config_data
    except Exception:
        return True
    return config_data.get("auto_enable_comfy_assets", True)

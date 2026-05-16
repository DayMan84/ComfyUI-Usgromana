# ComfyUI runs this before PromptServer is created (see main.py execute_prestartup_script).
# Relative imports are not available here — keep this file self-contained.
import json
import logging
import os

_log = logging.getLogger("usgromana")


def _auto_enable_requested() -> bool:
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f).get("auto_enable_comfy_assets", True)
    except Exception:
        return True


if _auto_enable_requested():
    try:
        from comfy.cli_args import args

        if not getattr(args, "enable_assets", False):
            args.enable_assets = True
            _log.info(
                "[Usgromana] Enabled ComfyUI assets system "
                "(no --enable-assets startup flag required)."
            )
        # Usgromana owns login; do not enable ComfyUI's built-in user picker (--multi-user UI).
        if getattr(args, "multi_user", False):
            args.multi_user = False
            _log.info(
                "[Usgromana] Disabled ComfyUI multi-user login screen "
                "(use Usgromana sign-in + Comfy-User header instead)."
            )
    except Exception as e:
        _log.debug("[Usgromana] Could not set args.enable_assets: %s", e)

    try:
        from comfy_api import feature_flags

        feature_flags.SERVER_FEATURE_FLAGS["assets"] = True
    except Exception as e:
        _log.debug("[Usgromana] Could not set feature_flags.assets: %s", e)

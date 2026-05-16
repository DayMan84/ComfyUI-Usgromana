# utils/sfw_intercept/reactor_sfw_intercept.py
# Canonical ReActor SFW intercept (used by __init__.py). Do not add a duplicate under utils/.

import importlib.util
import os
import sys

from ...globals import users_db, current_username_var


def _load_reactor_module():
    """
    Attempts to load reactor_sfw.py from any known comfyui-reactor location.
    Always fails silently and returns None if not found.
    """
    try:
        base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  
        # .../ComfyUI-Usgromana
        custom_nodes_dir = os.path.dirname(base)

        possible_names = [
            "comfyui-reactor-node",
            "ComfyUI-ReActor",
            "comfyui-reactor",
            "ComfyUI-Reactor",
        ]

        reactor_root = None
        for name in possible_names:
            candidate = os.path.join(custom_nodes_dir, name)
            if os.path.exists(os.path.join(candidate, "scripts", "reactor_sfw.py")):
                reactor_root = candidate
                break

        if not reactor_root:
            print("[Usgromana] Reactor plugin not found — continuing without it.")
            return None

        scripts_dir = os.path.join(reactor_root, "scripts")
        reactor_path = os.path.join(scripts_dir, "reactor_sfw.py")

        if not os.path.isfile(reactor_path):
            print("[Usgromana] reactor_sfw.py missing — skipping reactor patch.")
            return None

        if reactor_root not in sys.path:
            sys.path.insert(0, reactor_root)

        spec = importlib.util.spec_from_file_location("reactor_sfw", reactor_path)
        if not spec or not spec.loader:
            return None

        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    except Exception as e:
        print(f"[Usgromana] Silent Reactor load failure: {e}")
        return None


def _apply_patch():
    """
    Installs a per-user wrapper around reactor_sfw.nsfw_image().
    Silently skips if Reactor isn't installed.
    """
    reactor_sfw_mod = _load_reactor_module()
    if reactor_sfw_mod is None:
        return  # <-- SILENT EXIT

    if not hasattr(reactor_sfw_mod, "nsfw_image"):
        print("[Usgromana] reactor_sfw module found but nsfw_image missing.")
        return

    original = reactor_sfw_mod.nsfw_image
    print("[Usgromana] Reactor SFW patch installed.")

    def nsfw_image_patched(img_data, model_path):
        try:
            username = current_username_var.get(None)
        except LookupError:
            username = None

        sfw_flag = True
        if username:
            _, rec = users_db.get_user(username)
            if rec:
                sfw_flag = bool(rec.get("sfw_check", True))

        # Bypass path
        if sfw_flag is False:
            return False

        return original(img_data, model_path)

    reactor_sfw_mod.nsfw_image = nsfw_image_patched


# Never break the extension if patching fails.
try:
    _apply_patch()
except Exception as e:
    print(f"[Usgromana] Reactor intercept skipped (error: {e})")

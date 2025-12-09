# --- START OF FILE utils/nsfw_guard.py ---
import os
from functools import lru_cache
from typing import Optional, Tuple

from PIL import Image
from transformers import pipeline

import folder_paths
import comfy.model_management as model_management

from ...globals import users_db, current_username_var

# --- CONFIGURATION ---
# Using Falconsai for stricter detection
HF_MODEL_ID = "Falconsai/nsfw_image_detection"
MODEL_FOLDER_NAME = "falconsai-nsfw-image-detection"

# --- GLOBAL STATE (The Bridge) ---
# This variable holds the username of the person who most recently
# queued a prompt. It bridges the Web Server and the Worker Thread.
_LATEST_PROMPT_USER = "guest"

def set_latest_prompt_user(username: str | None):
    """
    Always update the worker-context username for the latest prompt.

    If we don't know the user, store 'guest' so we don't keep an old
    identity around from a previous request.
    """
    global _LATEST_PROMPT_USER

    effective = username or "guest"
    _LATEST_PROMPT_USER = effective

    # Debug so we can see it changing per prompt:
    print(f"[Usgromana::NSFWGuard] set_latest_prompt_user → {effective!r}")


@lru_cache(maxsize=1)
def _get_nsfw_pipeline():
    """
    Load the HuggingFace image-classification pipeline.
    Handles auto-downloading and device selection (CUDA/MPS/CPU).
    """
    base = folder_paths.base_path
    local_model_dir = os.path.join(base, "models", "nsfw_detector", MODEL_FOLDER_NAME)

    # 1. Determine Model Source (Local vs Cloud)
    if os.path.exists(os.path.join(local_model_dir, "config.json")):
        model_source = local_model_dir
        # print(f"[Usgromana::NSFWGuard] ✅ Loading local model from: {local_model_dir}")
    else:
        model_source = HF_MODEL_ID
        print(f"[Usgromana::NSFWGuard] ⚠️ Local model missing. Downloading: {HF_MODEL_ID}")

    # 2. Determine Compute Device
    device = model_management.get_torch_device()
    device_str = str(device)
    pipe_device = -1  # Default to CPU

    if "cuda" in device_str:
        try:
            # Handle "cuda:0" vs just "cuda"
            pipe_device = int(device_str.split(":")[1]) if ":" in device_str else 0
        except Exception:
            pipe_device = 0
    elif "mps" in device_str:
        # Mac Silicon support
        pipe_device = "mps"

    # 3. Initialize Pipeline
    try:
        clf = pipeline("image-classification", model=model_source, device=pipe_device)
        return clf
    except Exception as e:
        print(f"[Usgromana::NSFWGuard] ❌ CRITICAL: Failed to load NSFW model. Error: {e}")
        return None


def _classify_image_path(path: str) -> Optional[Tuple[str, float]]:
    """
    Helper to run classification on an image file path.
    Returns (label, score).
    """
    clf = _get_nsfw_pipeline()
    if clf is None:
        return None

    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            result = clf(img)
    except Exception as e:
        print(f"[Usgromana::NSFWGuard] Error reading image {path}: {e}")
        return None

    if not result:
        return None

    top = result[0]
    label = top.get("label", "").lower()
    score = float(top.get("score", 0.0))
    return label, score


def _resolve_effective_username() -> str:
    """
    Decide which username to use for policy:

    1. Try the ContextVar (HTTP request thread).
    2. If that's empty or 'guest', fall back to _LATEST_PROMPT_USER (worker bridge).
    3. If *everything* fails, use 'guest'.
    """
    global _LATEST_PROMPT_USER

    try:
        ctx_user = current_username_var.get(None)
    except LookupError:
        ctx_user = None

    # Prefer a non-guest ContextVar user if present
    if ctx_user and ctx_user != "guest":
        username = ctx_user
    elif _LATEST_PROMPT_USER:
        username = _LATEST_PROMPT_USER
    else:
        username = "guest"

    # Debug: see what the resolver is doing
    print(
        f"[Usgromana::NSFWGuard] DEBUG resolve_user: ctx={ctx_user!r} "
        f"latest={_LATEST_PROMPT_USER!r} -> using={username!r}"
    )

    return username


def is_sfw_enforced_for_current_session() -> bool:
    # 1. Try ContextVar (Web Request Thread)
    try:
        username = current_username_var.get(None)
    except LookupError:
        username = None

    # 2. Fallback to Global (Worker Execution Thread)
    if not username:
        username = _LATEST_PROMPT_USER

    # 3. Check Database
    sfw_flag = True  # default BLOCK
    if username:
        _, rec = users_db.get_user(username)
        if rec is not None:
            sfw_flag = rec.get("sfw_check", True)
            print(f"[Usgromana] 🛡️ Policy Check: User='{username}' | SFW={sfw_flag}")
        else:
            print(f"[Usgromana] ⚠️ User '{username}' not found in DB. Defaulting to BLOCK.")
    return sfw_flag


def should_block_image_for_current_user(path: str) -> bool:
    """
    Main function called by __init__.py middleware to check static files.
    """
    # 1. Check Permissions
    if not is_sfw_enforced_for_current_session():
        # User is trusted (sfw_check: false), skip scanning
        return False

    # 2. Check Image Content
    cls = _classify_image_path(path)
    if cls is None:
        # Fail open (allow) if model is broken
        return False

    label, score = cls

    # 3. Decision (Threshold 0.5)
    if label == "nsfw" and score > 0.5:
        print(
            f"[Usgromana::NSFWGuard] 🛑 BLOCKED NSFW file: "
            f"{os.path.basename(path)} (Score: {score:.2f})"
        )
        return True

    return False
# --- END OF FILE utils/nsfw_guard.py ---

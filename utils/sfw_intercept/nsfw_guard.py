# --- START OF FILE utils/nsfw_guard.py ---
import os
import json
from functools import lru_cache
from typing import Optional, Tuple, Dict

from PIL import Image
from PIL import PngImagePlugin
from PIL.ExifTags import TAGS
from transformers import pipeline

import folder_paths
import comfy.model_management as model_management

from ...globals import users_db, current_username_var

# --- CONFIGURATION ---
# Using Falconsai for stricter detection
HF_MODEL_ID = "Falconsai/nsfw_image_detection"
MODEL_FOLDER_NAME = "falconsai-nsfw-image-detection"

# NSFW Metadata Keys
NSFW_METADATA_KEY = "UsgromanaNSFW"
NSFW_SCORE_KEY = "UsgromanaNSFWScore"
NSFW_LABEL_KEY = "UsgromanaNSFWLabel"

# --- GLOBAL STATE (The Bridge) ---
# This variable holds the username of the person who most recently
# queued a prompt. It bridges the Web Server and the Worker Thread.
_LATEST_PROMPT_USER = "guest"

# Cache for SFW enforcement checks to avoid repeated DB lookups and logging
_SFW_CACHE = {}  # {username: (sfw_flag, last_logged_username)}
_LAST_LOGGED_USER = None


def _get_nsfw_tag(path: str) -> Optional[Dict]:
    """
    Get NSFW tag directly from image metadata.
    
    Returns:
        Dict with keys: is_nsfw, score, label
        or None if not tagged
    """
    try:
        if not os.path.exists(path):
            return None
        
        img = Image.open(path)
        ext = os.path.splitext(path)[1].lower()
        
        # For PNG: Check info metadata
        if ext in ('.png',):
            info = img.info
            # First check our custom keys (primary source)
            if NSFW_METADATA_KEY in info:
                is_nsfw = info.get(NSFW_METADATA_KEY, '').lower() == 'true'
                score = float(info.get(NSFW_SCORE_KEY, '0.0'))
                label = info.get(NSFW_LABEL_KEY, '')
                result = {
                    "is_nsfw": is_nsfw,
                    "score": score,
                    "label": label
                }
                return result
            
            # Fallback: Check Windows-readable Keywords field (if written by our code)
            if "Keywords" in info:
                keywords = str(info.get("Keywords", "")).lower()
                if "nsfw" in keywords:
                    # Found NSFW in Keywords, try to extract score from Comment
                    comment = str(info.get("Comment", ""))
                    score = 0.5  # Default score
                    label = "nsfw"
                    # Try to extract score from comment
                    import re
                    score_match = re.search(r'Score:\s*([\d.]+)', comment)
                    if score_match:
                        score = float(score_match.group(1))
                    result = {
                        "is_nsfw": True,
                        "score": score,
                        "label": label
                    }
                    return result
        
        # For JPEG: Check EXIF (both our custom tag and Windows-readable fields)
        elif ext in ('.jpg', '.jpeg'):
            try:
                # Try piexif first (more reliable)
                try:
                    import piexif
                    exif_dict = piexif.load(img.info.get('exif', b''))
                    
                    # Check our custom UserComment first
                    if "Exif" in exif_dict and piexif.ExifIFD.UserComment in exif_dict["Exif"]:
                        user_comment = exif_dict["Exif"][piexif.ExifIFD.UserComment]
                        if isinstance(user_comment, bytes):
                            user_comment = user_comment.decode('utf-8', errors='ignore')
                        if user_comment.startswith('NSFW:'):
                            try:
                                data = json.loads(user_comment[5:])
                                return {
                                    "is_nsfw": data.get("is_nsfw", False),
                                    "score": data.get("score", 0.0),
                                    "label": data.get("label", "")
                                }
                            except (json.JSONDecodeError, ValueError):
                                pass
                    
                    # Fallback: Check Windows XPKeywords field
                    if "0th" in exif_dict and piexif.ImageIFD.XPKeywords in exif_dict["0th"]:
                        keywords = exif_dict["0th"][piexif.ImageIFD.XPKeywords]
                        if isinstance(keywords, bytes):
                            keywords = keywords.decode('utf-16le', errors='ignore')
                        if "nsfw" in keywords.lower():
                            # Extract score from XPComment if available
                            score = 0.5
                            label = "nsfw"
                            if "0th" in exif_dict and piexif.ImageIFD.XPComment in exif_dict["0th"]:
                                comment = exif_dict["0th"][piexif.ImageIFD.XPComment]
                                if isinstance(comment, bytes):
                                    comment = comment.decode('utf-16le', errors='ignore')
                                import re
                                score_match = re.search(r'Score:\s*([\d.]+)', comment)
                                if score_match:
                                    score = float(score_match.group(1))
                            return {
                                "is_nsfw": True,
                                "score": score,
                                "label": label
                            }
                except ImportError:
                    # Fallback to PIL's basic EXIF
                    exif = img.getexif()
                    if exif:
                        # Use UserComment tag (0x9286)
                        user_comment = exif.get(0x9286)
                        if user_comment and isinstance(user_comment, (str, bytes)):
                            if isinstance(user_comment, bytes):
                                user_comment = user_comment.decode('utf-8', errors='ignore')
                            # Check if it's our NSFW data
                            if user_comment.startswith('NSFW:'):
                                try:
                                    data = json.loads(user_comment[5:])
                                    return {
                                        "is_nsfw": data.get("is_nsfw", False),
                                        "score": data.get("score", 0.0),
                                        "label": data.get("label", "")
                                    }
                                except (json.JSONDecodeError, ValueError):
                                    pass
            except Exception:
                pass
        
        # For other formats, try to read from info
        info = img.info
        if NSFW_METADATA_KEY in info:
            is_nsfw = info.get(NSFW_METADATA_KEY, '').lower() == 'true'
            score = float(info.get(NSFW_SCORE_KEY, '0.0'))
            label = info.get(NSFW_LABEL_KEY, '')
            return {
                "is_nsfw": is_nsfw,
                "score": score,
                "label": label
            }
        
    except Exception as e:
        # Fail silently - image may be corrupted or format not supported
        pass
    return None


def _set_nsfw_tag(path: str, is_nsfw: bool, score: float, label: str):
    """
    Set NSFW tag directly in image metadata.
    
    Args:
        path: Image file path
        is_nsfw: Whether image is NSFW
        score: Detection confidence score
        label: Detection label
    """
    try:
        if not os.path.exists(path):
            return
        
        img = Image.open(path)
        ext = os.path.splitext(path)[1].lower()
        
        # For PNG: Use PngInfo + Windows-compatible metadata
        if ext in ('.png',):
            # Read existing PNG info or create new
            pnginfo = PngImagePlugin.PngInfo()
            # Copy ALL existing text chunks (preserve existing metadata)
            # Exclude only the NSFW-related keys we're about to overwrite
            nsfw_keys_to_exclude = {NSFW_METADATA_KEY, NSFW_SCORE_KEY, NSFW_LABEL_KEY, "Keywords", "Subject", "Comment"}
            for key, value in img.info.items():
                # Preserve all metadata keys except NSFW ones we're overwriting
                if key not in nsfw_keys_to_exclude:
                    pnginfo.add_text(key, str(value))
            
            # Add NSFW metadata to PNG text chunks (for our code to read)
            pnginfo.add_text(NSFW_METADATA_KEY, str(is_nsfw).lower())
            pnginfo.add_text(NSFW_SCORE_KEY, str(score))
            pnginfo.add_text(NSFW_LABEL_KEY, label)
            
            # Also add to Windows-readable fields (Keywords/Tags field in Windows Properties)
            # Windows reads "Keywords" from PNG tEXt chunks - this is what shows in Properties > Details > Tags
            existing_keywords = img.info.get("Keywords", None)
            if is_nsfw:
                # Add to Keywords field (Windows Properties shows this in Tags)
                # Preserve existing keywords if they're not NSFW-related
                if existing_keywords and "nsfw" not in str(existing_keywords).lower():
                    pnginfo.add_text("Keywords", f"{existing_keywords}, NSFW")
                else:
                    pnginfo.add_text("Keywords", "NSFW")
                # Also add to Subject field
                pnginfo.add_text("Subject", f"NSFW Content (Score: {score:.2f})")
                # Add to Comments field (Windows Properties shows this)
                pnginfo.add_text("Comment", f"NSFW Content Detected - Score: {score:.2f}, Label: {label}")
            else:
                # If SFW, preserve existing Windows-readable fields (they're already excluded from preservation loop above)
                # So we don't need to add them back here - they're already preserved
                pass
            
            # Save with metadata
            img.save(path, "PNG", pnginfo=pnginfo, optimize=False)
        
        # For JPEG: Use EXIF (Windows-readable)
        elif ext in ('.jpg', '.jpeg'):
            try:
                # Try to use piexif for proper EXIF handling (if available)
                piexif_available = False
                try:
                    import piexif
                    piexif_available = True
                except ImportError:
                    pass
                if piexif_available:
                    # Load existing EXIF or create new
                    exif_dict = {}
                    try:
                        exif_dict = piexif.load(img.info.get('exif', b''))
                    except:
                        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}, "thumbnail": None}
                    
                    # Store NSFW data in UserComment (tag 0x9286 in Exif IFD)
                    nsfw_data = json.dumps({
                        "is_nsfw": is_nsfw,
                        "score": score,
                        "label": label
                    })
                    exif_dict["Exif"][piexif.ExifIFD.UserComment] = f"NSFW:{nsfw_data}".encode('utf-8')
                    
                    # Add to Windows-readable fields (only overwrite if NSFW, preserve existing if SFW)
                    if is_nsfw:
                        # Add to XPKeywords (Windows Tags field) - tag 0x9C9E in 0th IFD
                        # Preserve existing keywords if they're not NSFW-related
                        existing_xpkeywords = None
                        if "0th" in exif_dict and piexif.ImageIFD.XPKeywords in exif_dict["0th"]:
                            existing_xpkeywords = exif_dict["0th"][piexif.ImageIFD.XPKeywords]
                            if isinstance(existing_xpkeywords, bytes):
                                existing_xpkeywords = existing_xpkeywords.decode('utf-16le', errors='ignore')
                        if existing_xpkeywords and "nsfw" not in existing_xpkeywords.lower():
                            # Preserve existing keywords and append NSFW
                            exif_dict["0th"][piexif.ImageIFD.XPKeywords] = f"{existing_xpkeywords}, NSFW".encode('utf-16le')
                        else:
                            exif_dict["0th"][piexif.ImageIFD.XPKeywords] = "NSFW".encode('utf-16le')
                        # Add to XPSubject (Windows Subject field) - tag 0x9C9F
                        exif_dict["0th"][piexif.ImageIFD.XPSubject] = f"NSFW Content (Score: {score:.2f})".encode('utf-16le')
                        # Add to XPComment (Windows Comments field) - tag 0x9C9C
                        exif_dict["0th"][piexif.ImageIFD.XPComment] = f"NSFW Content Detected - Score: {score:.2f}, Label: {label}".encode('utf-16le')
                    # If SFW, preserve existing Windows-readable fields (don't overwrite)
                    
                    # Convert back to bytes and save
                    exif_bytes = piexif.dump(exif_dict)
                    img.save(path, "JPEG", quality=95, exif=exif_bytes, optimize=False)
                if not piexif_available:
                    # Fallback: Use PIL's basic EXIF (less reliable but no extra dependency)
                    exif_dict = {}
                    if hasattr(img, 'getexif'):
                        exif_dict = dict(img.getexif())
                    
                    # Store NSFW data as JSON in UserComment (tag 0x9286)
                    nsfw_data = json.dumps({
                        "is_nsfw": is_nsfw,
                        "score": score,
                        "label": label
                    })
                    exif_dict[0x9286] = f"NSFW:{nsfw_data}"
                    
                    # Convert to EXIF bytes
                    exif_bytes = img.getexif().tobytes() if hasattr(img.getexif(), 'tobytes') else None
                    
                    # Save with EXIF
                    img.save(path, "JPEG", quality=95, exif=exif_bytes if exif_bytes else None, optimize=False)
            except Exception as e:
                # If EXIF writing fails, at least try to save the image
                print(f"[Usgromana::NSFWGuard] Warning: Could not write EXIF to {path}: {e}")
                img.save(path, "JPEG", quality=95, optimize=False)
        
        # For other formats: Try to save in info
        else:
            # Create a copy with metadata in info
            info = img.info.copy()
            info[NSFW_METADATA_KEY] = str(is_nsfw).lower()
            info[NSFW_SCORE_KEY] = str(score)
            info[NSFW_LABEL_KEY] = label
            
            # Save with info (may not work for all formats)
            try:
                img.save(path, exif=img.getexif() if hasattr(img, 'getexif') else None, **info)
            except Exception:
                # Some formats don't support metadata, fail silently
                pass
        
    except Exception as e:
        # Fail silently - image may be read-only or format doesn't support metadata
        print(f"[Usgromana::NSFWGuard] Warning: Could not write metadata to {path}: {e}")


def set_nsfw_tag_manual(path: str, is_nsfw: bool, score: float = 1.0, label: str = "manual"):
    """
    Manually set NSFW tag on an image (for manual review/flagging).
    
    This function allows extensions to manually flag images as NSFW or SFW,
    bypassing automatic detection. Useful for gallery review workflows.
    
    Args:
        path: Image file path
        is_nsfw: True to mark as NSFW, False to mark as SFW
        score: Confidence score (default: 1.0 for manual flags)
        label: Detection label (default: "manual" to indicate manual flagging)
    
    Example:
        # Flag an image as NSFW
        set_nsfw_tag_manual("/output/image.png", is_nsfw=True)
        
        # Mark an image as safe
        set_nsfw_tag_manual("/output/image.png", is_nsfw=False)
    """
    _set_nsfw_tag(path, is_nsfw, score, label)


def clear_nsfw_tag(path: str):
    """
    Clear NSFW tag from image metadata (force rescan on next check).
    
    Args:
        path: Image file path
    """
    
    try:
        if not os.path.exists(path):
            return
        
        img = Image.open(path)
        ext = os.path.splitext(path)[1].lower()
        
        # For PNG: Remove from PngInfo (including Windows-readable fields)
        if ext in ('.png',):
            pnginfo = PngImagePlugin.PngInfo()
            # Copy existing text chunks except NSFW ones and Windows-readable NSFW fields
            excluded_keys = {NSFW_METADATA_KEY, NSFW_SCORE_KEY, NSFW_LABEL_KEY, "Keywords", "Subject", "Comment"}
            for key, value in img.info.items():
                if key not in excluded_keys:
                    if isinstance(key, str) and (key.startswith('text') or key in ('tEXt', 'iTXt', 'zTXt')):
                        # Only copy if it's not an NSFW-related Windows field
                        if not (key == "Keywords" and str(value).upper() in ("NSFW", "SFW")):
                            pnginfo.add_text(key, str(value))
            
            # Save without NSFW metadata
            img.save(path, "PNG", pnginfo=pnginfo, optimize=False)
        
        # For JPEG: Remove from EXIF
        elif ext in ('.jpg', '.jpeg'):
            
            # Try to use piexif for proper EXIF handling (if available)
            try:
                import piexif
                # Load existing EXIF
                exif_dict = {}
                try:
                    exif_dict = piexif.load(img.info.get('exif', b''))
                except:
                    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}, "thumbnail": None}
                
                # Remove NSFW data from UserComment
                if "Exif" in exif_dict and piexif.ExifIFD.UserComment in exif_dict["Exif"]:
                    user_comment = exif_dict["Exif"][piexif.ExifIFD.UserComment]
                    if isinstance(user_comment, bytes) and user_comment.startswith(b"NSFW:"):
                        del exif_dict["Exif"][piexif.ExifIFD.UserComment]
                
                # Remove Windows-readable fields
                if "0th" in exif_dict:
                    for tag in [piexif.ImageIFD.XPKeywords, piexif.ImageIFD.XPSubject, piexif.ImageIFD.XPComment]:
                        if tag in exif_dict["0th"]:
                            del exif_dict["0th"][tag]
                
                # Convert back to bytes and save
                exif_bytes = piexif.dump(exif_dict)
                img.save(path, "JPEG", quality=95, exif=exif_bytes, optimize=False)
            except ImportError:
                # Fallback: Use PIL's basic EXIF
                exif_dict = {}
                if hasattr(img, 'getexif'):
                    exif = img.getexif()
                    for tag_id, value in exif.items():
                        if tag_id != 0x9286 or (isinstance(value, str) and not value.startswith('NSFW:')):
                            exif_dict[tag_id] = value
                
                exif_bytes = None
                if exif_dict:
                    try:
                        exif_bytes = img.getexif().tobytes() if hasattr(img.getexif(), 'tobytes') else None
                    except Exception:
                        pass
                
                img.save(path, "JPEG", quality=95, exif=exif_bytes, optimize=False)
        
    except Exception as e:
        print(f"[Usgromana::NSFWGuard] Warning: Could not clear metadata from {path}: {e}")

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


def _classify_image_path(path: str, use_cache: bool = True) -> Optional[Tuple[str, float]]:
    """
    Helper to run classification on an image file path.
    Checks cache first, only scans if not cached.
    
    Args:
        path: Image file path
        use_cache: If True, check cache before scanning
    
    Returns:
        (label, score) tuple or None
    """
    # 1. Check cache first (fast path)
    if use_cache:
        tag = _get_nsfw_tag(path)
        if tag is not None:
            return tag.get("label", "").lower(), tag.get("score", 0.0)
    
    # 2. Scan image (slow path)
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
    
    # Find NSFW label in all results (hypothesis A: model returns multiple labels)
    nsfw_result = None
    normal_result = None
    for r in result:
        r_label = r.get("label", "").lower()
        r_score = float(r.get("score", 0.0))
        if r_label == "nsfw":
            nsfw_result = (r_label, r_score)
        elif r_label == "normal":
            normal_result = (r_label, r_score)
    
    # Use NSFW result if found, otherwise use first result (current behavior)
    if nsfw_result:
        label, score = nsfw_result
    else:
        top = result[0]
        label = top.get("label", "").lower()
        score = float(top.get("score", 0.0))
    
    # 3. Determine if NSFW (only trust model's explicit "nsfw" label)
    # Removed strict heuristic - it was causing too many false positives
    # Only block if model explicitly says "nsfw" with score > 0.5
    is_nsfw = (label == "nsfw" and score > 0.5)
    
    # Cache the result
    if use_cache:
        _set_nsfw_tag(path, is_nsfw, score, label)
    
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


def is_sfw_enforced_for_current_session(quiet: bool = False) -> bool:
    """
    Check if SFW is enforced for the current session.
    
    Args:
        quiet: If True, suppresses logging (useful for batch operations)
    
    Returns:
        bool: True if SFW is enforced, False otherwise
    """
    global _LAST_LOGGED_USER
    
    # 1. Try ContextVar (Web Request Thread)
    try:
        username = current_username_var.get(None)
    except LookupError:
        username = None

    # 2. Fallback to Global (Worker Execution Thread)
    if not username:
        username = _LATEST_PROMPT_USER
    
    # Normalize username for caching
    cache_key = username or "guest"

    # 3. Check cache first
    if cache_key in _SFW_CACHE:
        cached_flag, _ = _SFW_CACHE[cache_key]
        # Only log once per user session change, unless quiet mode
        if not quiet and _LAST_LOGGED_USER != cache_key:
            _LAST_LOGGED_USER = cache_key
            # Don't log every check, only on user change
        return cached_flag

    # 4. Check Database (cache miss)
    sfw_flag = True  # default BLOCK
    if username:
        _, rec = users_db.get_user(username)
        if rec is not None:
            sfw_flag = rec.get("sfw_check", True)
            # Cache the result
            _SFW_CACHE[cache_key] = (sfw_flag, username)
            # Only log on first check for this user, unless quiet mode
            if not quiet:
                if _LAST_LOGGED_USER != cache_key:
                    print(f"[Usgromana] 🛡️ Policy Check: User='{username}' | SFW={sfw_flag}")
                    _LAST_LOGGED_USER = cache_key
        else:
            # Cache the default
            _SFW_CACHE[cache_key] = (sfw_flag, username)
            if not quiet:
                if _LAST_LOGGED_USER != cache_key:
                    print(f"[Usgromana] ⚠️ User '{username}' not found in DB. Defaulting to BLOCK.")
                    _LAST_LOGGED_USER = cache_key
    else:
        # Cache the default for None/guest
        _SFW_CACHE[cache_key] = (sfw_flag, "guest")
    
    return sfw_flag


def clear_sfw_cache(username: str | None = None):
    """
    Clear the SFW enforcement cache.
    
    Args:
        username: If provided, only clear cache for this user. If None, clear all.
    """
    global _SFW_CACHE, _LAST_LOGGED_USER
    if username:
        cache_key = username or "guest"
        _SFW_CACHE.pop(cache_key, None)
        if _LAST_LOGGED_USER == cache_key:
            _LAST_LOGGED_USER = None
    else:
        _SFW_CACHE.clear()
        _LAST_LOGGED_USER = None


def should_block_image_for_current_user(path: str, quiet: bool = False, use_cache: bool = True) -> bool:
    """
    Main function called by __init__.py middleware to check static files.
    Uses cache for fast lookups - only scans if not cached.
    
    Args:
        path: Path to the image file
        quiet: If True, suppresses logging (useful for batch operations)
        use_cache: If True, check cache before scanning (default: True)
    """
    # 1. Check Permissions
    sfw_enforced = is_sfw_enforced_for_current_session(quiet=quiet)
    if not sfw_enforced:
        # User is trusted (sfw_check: false), skip scanning
        return False

    # 2. Check cache first (fast path)
    if use_cache:
        tag = _get_nsfw_tag(path)
        if tag is not None:
            cached_is_nsfw = tag.get("is_nsfw", False)
            
            # Only block if explicitly marked as NSFW in cache
            # Removed strict heuristic to avoid false positives
            if cached_is_nsfw:
                if not quiet:
                    cached_score = tag.get("score", 0.0)
                    print(
                        f"[Usgromana::NSFWGuard] 🛑 BLOCKED NSFW file (cached): "
                        f"{os.path.basename(path)} (Score: {cached_score:.2f})"
                    )
                return True
            else:
                # Cached as safe, allow
                return False

    # 3. Scan image (slow path, only if not cached)
    cls = _classify_image_path(path, use_cache=use_cache)
    if cls is None:
        # Fail open (allow) if model is broken
        return False

    label, score = cls

    # 4. Decision - only block if model explicitly says "nsfw"
    # Removed strict heuristic to avoid false positives on safe images
    should_block = (label == "nsfw" and score > 0.5)
    if should_block:
        if not quiet:
            print(
                f"[Usgromana::NSFWGuard] 🛑 BLOCKED NSFW file: "
                f"{os.path.basename(path)} (Score: {score:.2f})"
            )
        return True

    return False


def clear_all_nsfw_tags():
    """
    Clear all NSFW tags from all images in output directory.
    Note: This scans all images, which may be slow.
    
    Returns:
        int: Number of images that had tags cleared
    """
    import folder_paths
    output_dir = folder_paths.get_output_directory()
    
    cleared_count = 0
    total_images = 0
    error_count = 0
    
    print(f"[Usgromana::NSFWGuard] Starting to clear NSFW tags from output directory: {output_dir}")
    
    try:
        for root, dirs, files in os.walk(output_dir):
            
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    total_images += 1
                    path = os.path.join(root, file)
                    try:
                        
                        tag = _get_nsfw_tag(path)
                        if tag:
                            
                            clear_nsfw_tag(path)
                            cleared_count += 1
                    except Exception as e:
                        error_count += 1
                        print(f"[Usgromana::NSFWGuard] Error clearing tag from {path}: {e}")
    except Exception as e:
        print(f"[Usgromana::NSFWGuard] Critical error in clear_all_nsfw_tags: {e}")
    
    print(f"[Usgromana::NSFWGuard] Cleared NSFW tags from {cleared_count} images (out of {total_images} total images, {error_count} errors)")
    return cleared_count


def fix_incorrectly_cached_tags():
    """
    Fix images that were incorrectly marked as NSFW due to the strict heuristic.
    Re-evaluates cached tags: if label is "normal" but is_nsfw is True, clear the tag
    to force a rescan with the corrected logic.
    """
    import folder_paths
    output_dir = folder_paths.get_output_directory()
    
    fixed_count = 0
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                path = os.path.join(root, file)
                try:
                    tag = _get_nsfw_tag(path)
                    if tag:
                        cached_label = tag.get("label", "").lower()
                        cached_is_nsfw = tag.get("is_nsfw", False)
                        # If label is "normal" but is_nsfw is True, this was incorrectly cached
                        # Clear it to force rescan with correct logic
                        if cached_label == "normal" and cached_is_nsfw:
                            clear_nsfw_tag(path)
                            fixed_count += 1
                except Exception:
                    pass
    
    if fixed_count > 0:
        print(f"[Usgromana::NSFWGuard] Fixed {fixed_count} incorrectly cached images (cleared tags for rescan)")
    else:
        print(f"[Usgromana::NSFWGuard] No incorrectly cached images found")
    return fixed_count


def scan_all_images_in_output_directory(force_rescan: bool = False):
    """
    Scan all images in the output directory for NSFW content.
    Useful for batch scanning or forcing a rescan of all images.
    
    Args:
        force_rescan: If True, clear existing tags and rescan all images.
                     If False, only scan images without tags.
    
    Returns:
        dict with stats: {"scanned": int, "nsfw_found": int, "errors": int}
    """
    import folder_paths
    output_dir = folder_paths.get_output_directory()
    
    scanned_count = 0
    nsfw_count = 0
    error_count = 0
    
    print(f"[Usgromana::NSFWGuard] Starting batch scan of output directory: {output_dir}")
    
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                path = os.path.join(root, file)
                try:
                    # If force_rescan, clear existing tag first
                    if force_rescan:
                        clear_nsfw_tag(path)
                    
                    # Check if already tagged (skip if not forcing rescan)
                    if not force_rescan:
                        tag = _get_nsfw_tag(path)
                        if tag is not None:
                            # Already tagged, skip
                            if tag.get("is_nsfw", False):
                                nsfw_count += 1
                            continue
                    
                    # Scan the image
                    cls = _classify_image_path(path, use_cache=True)
                    if cls:
                        label, score = cls
                        scanned_count += 1
                        if label == "nsfw" and score > 0.5:
                            nsfw_count += 1
                except Exception as e:
                    error_count += 1
                    print(f"[Usgromana::NSFWGuard] Error scanning {path}: {e}")
    
    result = {
        "scanned": scanned_count,
        "nsfw_found": nsfw_count,
        "errors": error_count,
        "total_images": scanned_count + nsfw_count + error_count
    }
    
    print(f"[Usgromana::NSFWGuard] Batch scan complete: {result}")
    return result
# --- END OF FILE utils/nsfw_guard.py ---

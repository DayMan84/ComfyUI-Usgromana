"""
Public API for ComfyUI-Usgromana NSFW Guard

This module provides a public interface for other ComfyUI extensions to use
the NSFW guard functionality for validating user permissions and checking
NSFW content.

Example usage in another extension:

    try:
        from ComfyUI_Usgromana.api import (
            is_sfw_enforced_for_user,
            check_tensor_nsfw,
            check_image_path_nsfw,
            set_user_context
        )
        
        # Check if SFW is enforced for a specific user
        if is_sfw_enforced_for_user("username"):
            # User has SFW restrictions, check content
            if check_tensor_nsfw(image_tensor):
                # Block or replace the image
                pass
        
        # Or check an image file path
        if check_image_path_nsfw("/path/to/image.png"):
            # Block the image
            pass
            
    except ImportError:
        # Extension not installed, handle gracefully
        pass
"""

import sys
import os
from typing import Optional, Union

# Optional dependencies - will be imported when needed
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# Try to import the NSFW guard functions
# Handle multiple import strategies for maximum compatibility
_NSFW_GUARD_AVAILABLE = False
_is_sfw_enforced_for_current_session = None
_should_block_image_for_current_user = None
_set_latest_prompt_user = None
_get_nsfw_pipeline = None
_users_db = None
_current_username_var = None
_get_nsfw_tag = None
_clear_nsfw_tag = None
_clear_all_nsfw_tags = None
_set_nsfw_tag_manual = None

def _try_imports():
    """Try multiple import strategies to load internal functions."""
    global _NSFW_GUARD_AVAILABLE
    global _is_sfw_enforced_for_current_session
    global _should_block_image_for_current_user
    global _set_latest_prompt_user
    global _get_nsfw_pipeline
    global _users_db
    global _current_username_var
    global _get_nsfw_tag
    global _clear_nsfw_tag
    global _clear_all_nsfw_tags
    global _set_nsfw_tag_manual
    
    import sys
    import os
    
    # Strategy 1: Relative import (when imported as a package from __init__.py)
    try:
        from .utils.sfw_intercept.nsfw_guard import (
            is_sfw_enforced_for_current_session,
            should_block_image_for_current_user,
            set_latest_prompt_user,
            _get_nsfw_pipeline,
            _get_nsfw_tag,
            clear_nsfw_tag,
            clear_all_nsfw_tags,
            set_nsfw_tag_manual,
        )
        from .globals import users_db, current_username_var
        _is_sfw_enforced_for_current_session = is_sfw_enforced_for_current_session
        _should_block_image_for_current_user = should_block_image_for_current_user
        _set_latest_prompt_user = set_latest_prompt_user
        _get_nsfw_pipeline = _get_nsfw_pipeline
        _users_db = users_db
        _current_username_var = current_username_var
        _get_nsfw_tag = _get_nsfw_tag
        _clear_nsfw_tag = clear_nsfw_tag
        _clear_all_nsfw_tags = clear_all_nsfw_tags
        _set_nsfw_tag_manual = set_nsfw_tag_manual
        _NSFW_GUARD_AVAILABLE = True
        return True
    except (ImportError, ValueError, SystemError, AttributeError) as e:
        pass
    
    # Strategy 2: Absolute import from extension root (when path is added to sys.path)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    try:
        from utils.sfw_intercept.nsfw_guard import (
            is_sfw_enforced_for_current_session,
            should_block_image_for_current_user,
            set_latest_prompt_user,
            _get_nsfw_pipeline,
            _get_nsfw_tag,
            clear_nsfw_tag,
            clear_all_nsfw_tags,
            set_nsfw_tag_manual,
        )
        from globals import users_db, current_username_var
        _is_sfw_enforced_for_current_session = is_sfw_enforced_for_current_session
        _should_block_image_for_current_user = should_block_image_for_current_user
        _set_latest_prompt_user = set_latest_prompt_user
        _get_nsfw_pipeline = _get_nsfw_pipeline
        _users_db = users_db
        _current_username_var = current_username_var
        _get_nsfw_tag = _get_nsfw_tag
        _clear_nsfw_tag = clear_nsfw_tag
        _clear_all_nsfw_tags = clear_all_nsfw_tags
        _set_nsfw_tag_manual = set_nsfw_tag_manual
        _NSFW_GUARD_AVAILABLE = True
        return True
    except (ImportError, AttributeError) as e:
        pass
    
    # Strategy 3: Try importing using importlib (for when module name is known)
    try:
        import importlib
        # Try to find the module in sys.modules or by searching
        for module_name in sys.modules:
            if 'usgromana' in module_name.lower() or 'ComfyUI_Usgromana' in module_name:
                try:
                    mod = sys.modules[module_name]
                    if hasattr(mod, 'utils'):
                        nsfw_mod = mod.utils.sfw_intercept.nsfw_guard
                        globals_mod = mod.globals
                        _is_sfw_enforced_for_current_session = nsfw_mod.is_sfw_enforced_for_current_session
                        _should_block_image_for_current_user = nsfw_mod.should_block_image_for_current_user
                        _set_latest_prompt_user = nsfw_mod.set_latest_prompt_user
                        _get_nsfw_pipeline = nsfw_mod._get_nsfw_pipeline
                        _users_db = globals_mod.users_db
                        _current_username_var = globals_mod.current_username_var
                        _get_nsfw_tag = getattr(nsfw_mod, '_get_nsfw_tag', None)
                        _clear_nsfw_tag = getattr(nsfw_mod, 'clear_nsfw_tag', None)
                        _clear_all_nsfw_tags = getattr(nsfw_mod, 'clear_all_nsfw_tags', None)
                        _set_nsfw_tag_manual = getattr(nsfw_mod, 'set_nsfw_tag_manual', None)
                        _NSFW_GUARD_AVAILABLE = True
                        return True
                except (AttributeError, ImportError):
                    continue
    except Exception:
        pass
    
    # Strategy 4: Try to find and import by file path
    try:
        import importlib.util
        current_dir = os.path.dirname(os.path.abspath(__file__))
        nsfw_guard_path = os.path.join(current_dir, "utils", "sfw_intercept", "nsfw_guard.py")
        globals_path = os.path.join(current_dir, "globals.py")
        
        if os.path.exists(nsfw_guard_path) and os.path.exists(globals_path):
            # Load nsfw_guard module
            spec = importlib.util.spec_from_file_location("nsfw_guard", nsfw_guard_path)
            if spec and spec.loader:
                nsfw_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(nsfw_mod)
                
                # Load globals module
                spec_globals = importlib.util.spec_from_file_location("globals", globals_path)
                if spec_globals and spec_globals.loader:
                    globals_mod = importlib.util.module_from_spec(spec_globals)
                    spec_globals.loader.exec_module(globals_mod)
                    
                    _is_sfw_enforced_for_current_session = nsfw_mod.is_sfw_enforced_for_current_session
                    _should_block_image_for_current_user = nsfw_mod.should_block_image_for_current_user
                    _set_latest_prompt_user = nsfw_mod.set_latest_prompt_user
                    _get_nsfw_pipeline = nsfw_mod._get_nsfw_pipeline
                    _users_db = globals_mod.users_db
                    _current_username_var = globals_mod.current_username_var
                    _NSFW_GUARD_AVAILABLE = True
                    return True
    except Exception as e:
        pass
    
    return False

# Attempt to load the internal functions
_try_imports()


def is_available() -> bool:
    """
    Check if the NSFW guard API is available.
    
    Returns:
        bool: True if the NSFW guard is available, False otherwise
    """
    return _NSFW_GUARD_AVAILABLE


def is_sfw_enforced_for_user(username: Optional[str] = None) -> bool:
    """
    Check if SFW (Safe For Work) restrictions are enforced for a user.
    
    Args:
        username: Optional username to check. If None, checks the current session user.
    
    Returns:
        bool: True if SFW is enforced (user should be blocked from NSFW), 
              False if user is allowed to view NSFW content.
    
    Note:
        Guest users always have SFW enforced (returns True) regardless of database settings.
    
    Example:
        if is_sfw_enforced_for_user("john"):
            # User 'john' has SFW restrictions
            pass
    """
    if not _NSFW_GUARD_AVAILABLE:
        return False  # Fail open if extension not available
    
    if username is None:
        # Use current session context
        if _is_sfw_enforced_for_current_session:
            result = _is_sfw_enforced_for_current_session()
            # For guests, always enforce SFW
            current_user = get_current_user()
            if (not current_user or current_user.lower() == "guest") and not result:
                return True  # Force SFW enforcement for guests
            return result
        return True  # Default to enforced if function not available
    
    # Guest users always have SFW enforced
    if username and username.lower() == "guest":
        return True
    
    # Check specific user
    if _users_db:
        _, rec = _users_db.get_user(username)
        if rec is not None:
            return rec.get("sfw_check", True)  # Default to True (enforced)
    return True  # Default to enforced if user not found


def check_tensor_nsfw(images_tensor, threshold: float = 0.5) -> bool:
    """
    Check if an image tensor contains NSFW content.
    
    Args:
        images_tensor: PyTorch tensor containing image data (shape: [batch, channels, height, width])
        threshold: Confidence threshold for NSFW detection (default: 0.5)
    
    Returns:
        bool: True if NSFW content is detected above threshold, False otherwise.
              Returns False if SFW is not enforced for the current user.
    
    Example:
        if check_tensor_nsfw(image_tensor):
            # Replace with black image or block
            image_tensor = torch.zeros_like(image_tensor)
    """
    if not _NSFW_GUARD_AVAILABLE:
        return False  # Fail open
    
    if not TORCH_AVAILABLE or not PIL_AVAILABLE or not NUMPY_AVAILABLE:
        print("[Usgromana API] Required dependencies (torch, PIL, numpy) not available")
        return False  # Fail open
    
    # Get current user to check if guest
    current_user = get_current_user()
    is_guest = (not current_user or current_user.lower() == "guest")
    
    # First check if SFW is enforced for current user
    # For guests, always check the image regardless of session state
    if _is_sfw_enforced_for_current_session:
        # Use quiet mode to avoid excessive logging during batch operations
        try:
            sfw_enforced = _is_sfw_enforced_for_current_session(quiet=True)
        except TypeError:
            # Fallback if quiet parameter not supported (older version)
            sfw_enforced = _is_sfw_enforced_for_current_session()
        # If not enforced and not a guest, skip check
        if not sfw_enforced and not is_guest:
            return False  # User is allowed, skip check
        # For guests, always check even if session says not enforced
    elif not is_guest:
        # If we can't check and not a guest, fail open
        return False
    
    # Get the NSFW detection pipeline
    if not _get_nsfw_pipeline:
        return False  # Fail open if function not available
    pipeline = _get_nsfw_pipeline()
    if pipeline is None:
        return False  # Fail open if model not available
    
    try:
        if images_tensor is None or len(images_tensor) == 0:
            return False
        
        # Convert tensor to PIL Image
        i = 255. * images_tensor[0].cpu().numpy()
        img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
        
        # Run classification
        results = pipeline(img)
        if not results:
            return False
        
        top = results[0]
        label = top.get("label", "").lower()
        score = float(top.get("score", 0.0))
        
        # Check if NSFW and above threshold
        if label == "nsfw" and score > threshold:
            return True
        
        return False
    except Exception as e:
        print(f"[Usgromana API] Error checking tensor: {e}")
        return False  # Fail open on error


def check_image_path_nsfw(image_path: str, username: Optional[str] = None) -> bool:
    """
    Check if an image file contains NSFW content.
    
    Args:
        image_path: Path to the image file
        username: Optional username to check permissions for. If None, uses current session.
    
    Returns:
        bool: True if image should be blocked (NSFW detected and user has restrictions),
              False otherwise.
    
    Note:
        Guest users always have their images checked, regardless of session state.
    
    Example:
        if check_image_path_nsfw("/output/image.png", "john"):
            # Block access to this image
            return web.Response(status=403, text="NSFW Blocked")
    """
    if not _NSFW_GUARD_AVAILABLE:
        return False  # Fail open
    
    # Determine if this is a guest user
    is_guest = False
    if username is not None:
        is_guest = (username.lower() == "guest")
        # Check if SFW is enforced for the specific user
        # For guests, always check regardless of setting
        if not is_guest and not is_sfw_enforced_for_user(username):
            return False  # User allowed, skip check
    else:
        # Check current user
        current_user = get_current_user()
        is_guest = (not current_user or current_user.lower() == "guest")
        # For guests, always check. For others, check if SFW is enforced
        if not is_guest:
            if _is_sfw_enforced_for_current_session:
                # Use quiet mode to avoid excessive logging during batch operations
                try:
                    if not _is_sfw_enforced_for_current_session(quiet=True):
                        return False  # Current user allowed, skip check
                except TypeError:
                    # Fallback if quiet parameter not supported (older version)
                    if not _is_sfw_enforced_for_current_session():
                        return False  # Current user allowed, skip check
            else:
                return False  # Can't check, fail open
    
    # Use the existing function if available, otherwise do manual check
    if _should_block_image_for_current_user:
        # Temporarily set user context if needed for the check
        original_user = get_current_user()
        try:
            if username and username != original_user:
                set_user_context(username)
            # Use quiet mode to avoid excessive logging during batch operations
            try:
                result = _should_block_image_for_current_user(image_path, quiet=True)
            except TypeError:
                # Fallback if quiet parameter not supported (older version)
                result = _should_block_image_for_current_user(image_path)
            return result
        finally:
            if username and username != original_user:
                set_user_context(original_user)
    else:
        # Fallback: manual check using the pipeline
        if not _get_nsfw_pipeline:
            return False
        pipeline = _get_nsfw_pipeline()
        if pipeline is None:
            return False
        
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                img = img.convert("RGB")
                results = pipeline(img)
                if results and len(results) > 0:
                    top = results[0]
                    label = top.get("label", "").lower()
                    score = float(top.get("score", 0.0))
                    if label == "nsfw" and score > 0.5:
                        return True
        except Exception as e:
            print(f"[Usgromana API] Error checking image path: {e}")
            return False
    
    return False


def check_pil_image_nsfw(image, threshold: float = 0.5) -> bool:
    """
    Check if a PIL Image contains NSFW content.
    
    Args:
        image: PIL Image object
        threshold: Confidence threshold for NSFW detection (default: 0.5)
    
    Returns:
        bool: True if NSFW content is detected above threshold, False otherwise.
              Returns False if SFW is not enforced for the current user.
    
    Example:
        pil_image = Image.open("image.png")
        if check_pil_image_nsfw(pil_image):
            # Block or replace image
            pass
    """
    if not _NSFW_GUARD_AVAILABLE:
        return False  # Fail open
    
    if not PIL_AVAILABLE:
        print("[Usgromana API] PIL (Pillow) not available")
        return False  # Fail open
    
    # Get current user to check if guest
    current_user = get_current_user()
    is_guest = (not current_user or current_user.lower() == "guest")
    
    # First check if SFW is enforced for current user
    # For guests, always check the image regardless of session state
    if _is_sfw_enforced_for_current_session:
        # Use quiet mode to avoid excessive logging during batch operations
        try:
            sfw_enforced = _is_sfw_enforced_for_current_session(quiet=True)
        except TypeError:
            # Fallback if quiet parameter not supported (older version)
            sfw_enforced = _is_sfw_enforced_for_current_session()
        # If not enforced and not a guest, skip check
        if not sfw_enforced and not is_guest:
            return False  # User is allowed, skip check
        # For guests, always check even if session says not enforced
    elif not is_guest:
        # If we can't check and not a guest, fail open
        return False
    
    # Get the NSFW detection pipeline
    if not _get_nsfw_pipeline:
        return False  # Fail open if function not available
    pipeline = _get_nsfw_pipeline()
    if pipeline is None:
        return False  # Fail open if model not available
    
    try:
        # Ensure RGB format
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        # Run classification
        results = pipeline(image)
        if not results:
            return False
        
        top = results[0]
        label = top.get("label", "").lower()
        score = float(top.get("score", 0.0))
        
        # Check if NSFW and above threshold
        if label == "nsfw" and score > threshold:
            return True
        
        return False
    except Exception as e:
        print(f"[Usgromana API] Error checking PIL image: {e}")
        return False  # Fail open on error


def set_user_context(username: Optional[str]):
    """
    Set the user context for the current execution thread.
    
    This is useful when you need to set the user context in a worker thread
    where the HTTP request context is not available.
    
    Args:
        username: Username to set as the current context, or None for guest
    
    Example:
        # In a worker thread
        set_user_context("john")
        # Now NSFW checks will use "john" as the user
    """
    if not _NSFW_GUARD_AVAILABLE:
        return
    
    if _set_latest_prompt_user:
        _set_latest_prompt_user(username)


def get_current_user() -> Optional[str]:
    """
    Get the current user from the context.
    
    Returns:
        Optional[str]: Current username, or None if not set
    
    Example:
        username = get_current_user()
        if username:
            print(f"Current user: {username}")
    """
    if not _NSFW_GUARD_AVAILABLE:
        return None
    
    if _current_username_var:
        try:
            return _current_username_var.get(None)
        except LookupError:
            return None
    return None


def check_image_path_nsfw_fast(image_path: str, username: Optional[str] = None) -> Optional[bool]:
    """
    Fast tag-only check for NSFW content. Only checks cache, never scans.
    Use this for bulk operations where you want instant results.
    
    Args:
        image_path: Path to the image file
        username: Optional username to check permissions for. If None, uses current session.
    
    Returns:
        bool: True if NSFW (block), False if safe (allow), None if not tagged yet (needs scan)
    
    Example:
        result = check_image_path_nsfw_fast("/output/image.png")
        if result is None:
            # Not tagged yet, do full scan or allow
            result = check_image_path_nsfw("/output/image.png")
        if result:
            # Block the image
            pass
    """
    if not _NSFW_GUARD_AVAILABLE or not _get_nsfw_tag:
        return None  # Can't check tags
    
    # Check if SFW is enforced
    if username is not None:
        if not is_sfw_enforced_for_user(username):
            return False  # User allowed, don't block
    else:
        current_user = get_current_user()
        is_guest = (not current_user or current_user.lower() == "guest")
        if not is_guest:
            if _is_sfw_enforced_for_current_session:
                try:
                    if not _is_sfw_enforced_for_current_session(quiet=True):
                        return False  # User allowed
                except TypeError:
                    if not _is_sfw_enforced_for_current_session():
                        return False
    
    # Check tag only (fast path)
    tag = _get_nsfw_tag(image_path)
    if tag is not None:
        return tag.get("is_nsfw", False)
    
    return None  # Not tagged yet, needs scan


def clear_image_nsfw_tag(image_path: str):
    """
    Clear NSFW tag for an image, forcing rescan on next check.
    
    Args:
        image_path: Path to the image file
    """
    if not _NSFW_GUARD_AVAILABLE or not _clear_nsfw_tag:
        return
    
    _clear_nsfw_tag(image_path)


def clear_all_nsfw_tags():
    """
    Clear all NSFW tags, forcing rescan of all images.
    """
    if not _NSFW_GUARD_AVAILABLE or not _clear_all_nsfw_tags:
        return
    
    _clear_all_nsfw_tags()


def set_image_nsfw_tag(image_path: str, is_nsfw: bool, score: float = 1.0, label: str = "manual") -> bool:
    """
    Manually set NSFW tag on an image (for manual review/flagging).
    
    This function allows extensions to manually flag images as NSFW or SFW,
    bypassing automatic detection. Useful for gallery review workflows.
    
    Args:
        image_path: Path to the image file
        is_nsfw: True to mark as NSFW, False to mark as SFW
        score: Confidence score (default: 1.0 for manual flags)
        label: Detection label (default: "manual" to indicate manual flagging)
    
    Returns:
        bool: True if successful, False otherwise
    
    Example:
        # Flag an image as NSFW
        set_image_nsfw_tag("/output/image.png", is_nsfw=True)
        
        # Mark an image as safe
        set_image_nsfw_tag("/output/image.png", is_nsfw=False)
    """
    if not _NSFW_GUARD_AVAILABLE or not _set_nsfw_tag_manual:
        return False
    
    try:
        _set_nsfw_tag_manual(image_path, is_nsfw, score, label)
        return True
    except Exception as e:
        print(f"[Usgromana API] Error setting NSFW tag: {e}")
        return False


# Export the public API
__all__ = [
    "is_available",
    "is_sfw_enforced_for_user",
    "check_tensor_nsfw",
    "check_image_path_nsfw",
    "check_image_path_nsfw_fast",
    "check_pil_image_nsfw",
    "set_user_context",
    "get_current_user",
    "clear_image_nsfw_tag",
    "clear_all_nsfw_tags",
    "set_image_nsfw_tag",
]


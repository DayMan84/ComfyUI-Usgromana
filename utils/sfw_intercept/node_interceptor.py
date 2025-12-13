# --- START OF FILE utils/node_interceptor.py ---
import torch
import nodes
import numpy as np
from PIL import Image
import latent_preview

from ...utils.sfw_intercept.nsfw_guard import (
    _get_nsfw_pipeline,
    is_sfw_enforced_for_current_session,
)
# --- CONFIGURATION ---
SCORE_THRESHOLD = 0.50  

# ----------------------------------------------------------------------------
# PART 1: The Scanner
# ----------------------------------------------------------------------------
def check_tensor_nsfw(images_tensor):
    # 1. CHECK USER PERMISSIONS FIRST
    # Use quiet mode to reduce logging during node execution
    if not is_sfw_enforced_for_current_session(quiet=True):
        # print("[Usgromana] 🛡️ SFW Disabled for this user. Bypassing scan.")
        return False

    # 2. Run Scan
    print("[Usgromana] 🔍 Interceptor: Analysis starting...")
    pipeline = _get_nsfw_pipeline()
    if pipeline is None:
        print("[Usgromana] ⚠️ WARN: Model failed. BLOCKING (Fail-Safe).")
        return True 

    try:
        if images_tensor is None or len(images_tensor) == 0: return False
        
        i = 255. * images_tensor[0].cpu().numpy()
        img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
        
        results = pipeline(img)
        # print(f"[Usgromana] 🔍 Raw Output: {results}")

        if not results: return False
            
        top = results[0]
        label = top.get("label", "").lower()
        score = float(top.get("score", 0.0))
        
        print(f"[Usgromana] 🔍 Decision: Label='{label}' Score={score:.4f}")

        if label == "nsfw" and score > SCORE_THRESHOLD:
            print(f"[Usgromana] 🛑 BLOCKED NSFW (Score {score:.4f})")
            return True
            
    except Exception as e:
        print(f"[Usgromana] ❌ Interceptor Error: {e}")
        return True 
    
    return False

# ----------------------------------------------------------------------------
# PART 2: The Kill Switch
# ----------------------------------------------------------------------------
def disable_latent_previews():
    # Only disable previews if the CURRENT user needs protection
    # But since previewers are global singletons in ComfyUI, 
    # we default to disabling them globally to be safe.
    print("[Usgromana] 🛡️ Disabling Latent Previews (Safe Mode)...")
    
    class SafeDummyPreviewer:
        def __init__(self, latent_format=None): pass
        def check_preview(self, i, preview_every, total_steps):
            if preview_every == 0: return False
            return (i % preview_every) == 0
        def decode_latent_to_preview_image(self, preview_format, x0):
            return None # Return None = No Image
        def close(self): pass

    def safe_get_previewer(device, latent_format):
        return SafeDummyPreviewer(latent_format)
        
    latent_preview.get_previewer = safe_get_previewer

# ----------------------------------------------------------------------------
# PART 3: The Interceptor (Wrapper)
# ----------------------------------------------------------------------------
def install_node_interceptor():
    disable_latent_previews()
    print("[Usgromana] 🛡️ Installing Node-Level Image Interceptor...")

    try:
        original_save = nodes.SaveImage.save_images
        original_preview = nodes.PreviewImage.save_images
    except AttributeError:
        return

    def intercepted_wrapper(self, images, filename_prefix="ComfyUI", prompt=None, extra_pnginfo=None, mode="unknown"):
        is_bad = check_tensor_nsfw(images)

        if is_bad:
            print(f"[Usgromana] 🛑 BLOCKED {mode}: Replacing with BLACK SQUARE.")
            black_images = torch.zeros_like(images)
            if mode == "save":
                return original_save(self, black_images, filename_prefix, prompt, extra_pnginfo)
            else:
                return original_preview(self, black_images, filename_prefix, prompt, extra_pnginfo)
        
        if mode == "save":
            return original_save(self, images, filename_prefix, prompt, extra_pnginfo)
        else:
            return original_preview(self, images, filename_prefix, prompt, extra_pnginfo)

    def save_patch(self, images, filename_prefix="ComfyUI", prompt=None, extra_pnginfo=None):
        return intercepted_wrapper(self, images, filename_prefix, prompt, extra_pnginfo, mode="save")

    def preview_patch(self, images, filename_prefix="ComfyUI", prompt=None, extra_pnginfo=None):
        return intercepted_wrapper(self, images, filename_prefix, prompt, extra_pnginfo, mode="preview")

    nodes.SaveImage.save_images = save_patch
    nodes.PreviewImage.save_images = preview_patch
    print("[Usgromana] 🛡️ Node Interceptor Active.")
# --- END OF FILE utils/node_interceptor.py ---

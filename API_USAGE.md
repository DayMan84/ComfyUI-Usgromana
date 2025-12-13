# NSFW Guard API Usage Guide

This guide explains how other ComfyUI extensions can use the NSFW Guard functionality from ComfyUI-Usgromana.

## Overview

The NSFW Guard API allows other extensions to:
- Check if a user has SFW (Safe For Work) restrictions enabled
- Validate image tensors, PIL Images, or image file paths for NSFW content
- Set user context for worker threads
- Get the current user from context

## Installation

Ensure that `ComfyUI-Usgromana` is installed in your ComfyUI `custom_nodes` directory. The extension must be loaded before your extension tries to use the API.

## Import Methods

### Method 1: Direct Import (Recommended)

Add the extension path to `sys.path` and import directly:

```python
import sys
import os

# Add ComfyUI-Usgromana to the path
extension_path = os.path.join(
    os.path.dirname(__file__),  # Your extension's directory
    "..",  # Go up to custom_nodes
    "ComfyUI-Usgromana"  # Usgromana extension folder
)
extension_path = os.path.abspath(extension_path)

if extension_path not in sys.path:
    sys.path.insert(0, extension_path)

try:
    from api import (
        is_available,
        is_sfw_enforced_for_user,
        check_tensor_nsfw,
        check_image_path_nsfw,
        check_pil_image_nsfw,
        set_user_context,
        get_current_user,
    )
    NSFW_GUARD_AVAILABLE = True
except ImportError:
    NSFW_GUARD_AVAILABLE = False
    print("[YourExtension] ComfyUI-Usgromana not found. NSFW guard unavailable.")
```

### Method 2: Using importlib

```python
import importlib.util
import os
import sys

def load_usgromana_api():
    """Load the Usgromana API module."""
    extension_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "ComfyUI-Usgromana"
    )
    api_path = os.path.join(extension_path, "api.py")
    
    if not os.path.exists(api_path):
        return None
    
    spec = importlib.util.spec_from_file_location("usgromana_api", api_path)
    if spec is None or spec.loader is None:
        return None
    
    module = importlib.util.module_from_spec(spec)
    sys.modules["usgromana_api"] = module
    spec.loader.exec_module(module)
    return module

# Load the API
usgromana_api = load_usgromana_api()
if usgromana_api and usgromana_api.is_available():
    # Use the API
    pass
```

## API Functions

### `is_available() -> bool`

Check if the NSFW guard API is available.

```python
if is_available():
    # API is ready to use
    pass
```

### `is_sfw_enforced_for_user(username: Optional[str] = None) -> bool`

Check if SFW restrictions are enforced for a user.

- **Parameters:**
  - `username`: Optional username. If `None`, checks the current session user.
- **Returns:** `True` if SFW is enforced (user should be blocked from NSFW), `False` if allowed.

```python
# Check current user
if is_sfw_enforced_for_user():
    # Current user has restrictions
    pass

# Check specific user
if is_sfw_enforced_for_user("john"):
    # User 'john' has restrictions
    pass
```

### `check_tensor_nsfw(images_tensor: torch.Tensor, threshold: float = 0.5) -> bool`

Check if an image tensor contains NSFW content.

- **Parameters:**
  - `images_tensor`: PyTorch tensor with shape `[batch, channels, height, width]`
  - `threshold`: Confidence threshold (default: 0.5)
- **Returns:** `True` if NSFW detected above threshold, `False` otherwise.

```python
import torch

# In your node's execution
def execute(self, image):
    if check_tensor_nsfw(image):
        # Replace with black image or raise error
        image = torch.zeros_like(image)
        # Or raise an exception
        # raise Exception("NSFW content detected")
    return image
```

### `check_image_path_nsfw(image_path: str, username: Optional[str] = None) -> bool`

Check if an image file should be blocked.

- **Parameters:**
  - `image_path`: Path to the image file
  - `username`: Optional username. If `None`, uses current session.
- **Returns:** `True` if image should be blocked, `False` otherwise.

```python
# In a web route handler
from aiohttp import web

async def view_image(request):
    image_path = "/path/to/image.png"
    username = get_user_from_request(request)
    
    if check_image_path_nsfw(image_path, username):
        return web.Response(status=403, text="NSFW Blocked")
    
    # Serve the image
    return web.FileResponse(image_path)
```

### `check_pil_image_nsfw(image: Image.Image, threshold: float = 0.5) -> bool`

Check if a PIL Image contains NSFW content.

- **Parameters:**
  - `image`: PIL Image object
  - `threshold`: Confidence threshold (default: 0.5)
- **Returns:** `True` if NSFW detected, `False` otherwise.

```python
from PIL import Image

image = Image.open("image.png")
if check_pil_image_nsfw(image):
    # Block or replace image
    image = Image.new("RGB", image.size, (0, 0, 0))
```

### `set_user_context(username: Optional[str])`

Set the user context for the current execution thread. Useful in worker threads where HTTP context is unavailable.

```python
# In a worker thread
set_user_context("john")
# Now NSFW checks will use "john" as the user
result = check_tensor_nsfw(image_tensor)
```

### `get_current_user() -> Optional[str]`

Get the current user from context.

```python
username = get_current_user()
if username:
    print(f"Current user: {username}")
```

## Complete Example

Here's a complete example of a custom node that uses the NSFW guard:

```python
import torch
import sys
import os

# Setup import path
extension_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "ComfyUI-Usgromana"
)
if extension_path not in sys.path:
    sys.path.insert(0, extension_path)

try:
    from api import (
        is_available,
        is_sfw_enforced_for_user,
        check_tensor_nsfw,
    )
    NSFW_GUARD_AVAILABLE = is_available()
except ImportError:
    NSFW_GUARD_AVAILABLE = False

class MyCustomNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
            }
        }
    
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"
    CATEGORY = "image"
    
    def execute(self, image):
        # Check if NSFW guard is available
        if NSFW_GUARD_AVAILABLE:
            # Check if current user has SFW restrictions
            if is_sfw_enforced_for_user():
                # Check the image tensor
                if check_tensor_nsfw(image):
                    # Replace with black image
                    print("[MyNode] NSFW content detected, blocking...")
                    image = torch.zeros_like(image)
        
        return (image,)
```

## Error Handling

Always check if the API is available before using it:

```python
if not is_available():
    # Extension not installed or not loaded
    # Handle gracefully - either skip checks or use alternative logic
    return image  # or your default behavior
```

## Notes

1. **Fail-Open Behavior**: If the NSFW guard is unavailable or encounters errors, it returns `False` (allows content). This ensures your extension continues to work even if Usgromana is not installed.

2. **User Context**: The API automatically resolves the current user from:
   - HTTP request context (for web routes)
   - Worker thread context (set via `set_user_context`)
   - Falls back to "guest" if no user is found

3. **Performance**: NSFW detection uses a HuggingFace model. The first check may be slower as the model loads. Subsequent checks are faster.

4. **Threshold**: The default threshold is 0.5. You can adjust it, but 0.5 is recommended for balanced detection.

## Troubleshooting

### ImportError when importing api

- Ensure ComfyUI-Usgromana is installed in `custom_nodes/ComfyUI-Usgromana`
- Check that the extension loaded successfully (check ComfyUI console)
- Verify the path is correct when adding to `sys.path`

### API returns False even when it should block

- Check that the user has `sfw_check: true` in their user record
- Verify the model loaded successfully (check console for errors)
- Ensure user context is set correctly (use `set_user_context` in worker threads)

### Model not loading

- The model downloads automatically on first use
- Check internet connection
- Verify you have enough disk space in `models/nsfw_detector/`
- Check console for specific error messages


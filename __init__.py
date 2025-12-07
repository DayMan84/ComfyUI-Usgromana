# --- START OF FILE __init__.py ---
from aiohttp import web
from .nodes import *
from .constants import FORCE_HTTPS, SEPERATE_USERS, MATCH_HEADERS

# Import globals
from .globals import (
    app, ip_filter, sanitizer, timeout, jwt_auth, 
    access_control, instance
)
from .utils import watcher 
from .utils.bootstrap import ensure_groups_config
from .routes import static, auth, admin, user, workflow_routes
import server 

WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "WEB_DIRECTORY"]

ensure_groups_config()

if FORCE_HTTPS:
    from .utils.force_https import create_https_middleware
    app.middlewares.append(create_https_middleware(MATCH_HEADERS))

app.middlewares.append(ip_filter.create_ip_filter_middleware())
app.middlewares.append(sanitizer.create_sanitizer_middleware())
app.middlewares.append(timeout.create_time_out_middleware(limited=("/login", "/register")))
app.middlewares.append(jwt_auth.create_jwt_middleware(
    public=("/login", "/logout", "/register"), 
    public_prefixes=("/usgromana", "/assets", "/static")
))

if SEPERATE_USERS:
    app.middlewares.append(access_control.create_folder_access_control_middleware())
    access_control.patch_folder_paths()
    access_control.patch_prompt_queue()

app.middlewares.append(access_control.create_usgromana_middleware())

watcher.register(app)

# --- NEW: WORKFLOW INTERCEPTION MIDDLEWARE ---
@web.middleware
async def workflow_interceptor_middleware(request, handler):
    """
    Checks if the request is for userdata/workflows.
    If so, hands it off to our logic and bypasses ComfyUI completely.
    """
    # 1. Ask our dispatcher if it wants to handle this request
    response = await workflow_routes.middleware_dispatch(request)
    
    # 2. If it handled it, return the response immediately
    if response is not None:
        return response
        
    # 3. If not, pass control back to ComfyUI
    return await handler(request)

# Register it (Last added = First executed in aiohttp middleware chain)
app.middlewares.append(workflow_interceptor_middleware)

print("------------------------------------------")
print("[Usgromana] Security System Initialized.")
print("[Usgromana] Workflow Storage Interceptor Active.")
print("------------------------------------------")

# --- START OF FILE __init__.py ---
from aiohttp import web
import os
import folder_paths
from .nodes import *
from .constants import FORCE_HTTPS, SEPERATE_USERS, MATCH_HEADERS
from .globals import (
    app, ip_filter, sanitizer, timeout, jwt_auth, access_control, 
    instance, current_username_var
)
from .utils import watcher
from .utils.bootstrap import ensure_groups_config
from .routes import static, auth, admin, user, workflow_routes
from .utils.sfw_intercept.reactor_sfw_intercept import _load_reactor_module
from .utils.sfw_intercept.nsfw_guard import should_block_image_for_current_user, set_latest_prompt_user
from .utils.sfw_intercept.node_interceptor import install_node_interceptor

import server

WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "WEB_DIRECTORY"]

ensure_groups_config()

# ---------------- Core middlewares ----------------
if FORCE_HTTPS:
    from .utils.force_https import create_https_middleware
    app.middlewares.append(create_https_middleware(MATCH_HEADERS))

app.middlewares.append(ip_filter.create_ip_filter_middleware())
app.middlewares.append(sanitizer.create_sanitizer_middleware())
app.middlewares.append(timeout.create_time_out_middleware(limited=("/login", "/register")))
app.middlewares.append(jwt_auth.create_jwt_middleware(public=("/login", "/logout", "/register"), public_prefixes=("/usgromana", "/assets", "/static")))

if SEPERATE_USERS:
    app.middlewares.append(access_control.create_folder_access_control_middleware())
    access_control.patch_folder_paths()
    access_control.patch_prompt_queue()

app.middlewares.append(access_control.create_usgromana_middleware())
watcher.register(app)

# --- WORKFLOW + GLOBAL SFW INTERCEPTION MIDDLEWARE ---
@web.middleware
async def workflow_interceptor_middleware(request, handler):
    path = request.path
    method = request.method

    # 1. Dispatcher
    response = await workflow_routes.middleware_dispatch(request)
    if isinstance(response, web.StreamResponse):
        return response

    # 2. User Resolution (With Debugging)
    username = "guest"
    try:
        # Try to get user from request first (if jwt_auth middleware attached it)
        if hasattr(request, "user") and request.user:
            username = request.user.get("username", "guest")
        else:
            # Fallback to manual decoding
            username = workflow_routes.get_current_user(request)
    except Exception:
        username = "guest"
    
    # Store for context access
    current_username_var.set(username)

    # --- USER CAPTURE FOR WORKER THREAD ---
    if path == "/prompt" and method in ("POST", "PUT"):
        # DEBUGGING: Print exact auth details for the prompt request
        # This will tell us if the Cookie is missing or the Token is invalid.
        # token = jwt_auth.get_token_from_request(request)
        # has_cookie = "access_token" in request.cookies
        # print(f"[Usgromana] 📡 PROMPT REQ | User: {username} | HasCookie: {has_cookie} | TokenLen: {len(str(token)) if token else 0}")
        
        # Force update the worker thread variable
        set_latest_prompt_user(username)

    # --- Case A: /view ---
    if path == "/view" and method == "GET":
        q = request.rel_url.query
        filename = q.get("filename") or q.get("file") or q.get("name")
        img_type = q.get("type", "output")

        if filename and (img_type == "output" or img_type == "temp"):
            if img_type == "temp":
                target_dir = folder_paths.get_temp_directory()
            else:
                target_dir = folder_paths.get_output_directory()
                
            img_path = os.path.join(target_dir, filename)

            if os.path.isfile(img_path):
                if should_block_image_for_current_user(img_path):
                    return web.Response(status=403, text="NSFW Blocked")

    # --- Case B: /static_gallery ---
    if path.startswith("/static_gallery/") and method == "GET":
        rel = path[len("/static_gallery/") :].lstrip("/\\")
        out_dir = folder_paths.get_output_directory()
        img_path = os.path.join(out_dir, rel)
        if os.path.isfile(img_path) and should_block_image_for_current_user(img_path):
             return web.Response(status=403, text="NSFW Blocked")

    return await handler(request)

app.middlewares.append(workflow_interceptor_middleware)
install_node_interceptor() 

print("------------------------------------------")
print("[Usgromana] Security System Initialized.")
print("[Usgromana] Workflow Storage Interceptor Active.")
print("------------------------------------------")
# --- END OF FILE __init__.py ---

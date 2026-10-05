# --- START OF FILE __init__.py ---
from aiohttp import web
import os
import folder_paths

from .utils.enable_comfy_assets import assets_enable_requested, enable_comfy_assets
from .utils.asyncio_client_disconnect import install_asyncio_disconnect_quiet_handler

install_asyncio_disconnect_quiet_handler()

if assets_enable_requested():
    enable_comfy_assets(log=False)

from .nodes import *
from .constants import FORCE_HTTPS, SEPARATE_USERS, MATCH_HEADERS
from .globals import (
    app, ip_filter, sanitizer, timeout, jwt_auth, access_control,
    instance, current_username_var
)
from .utils import watcher
from .utils.bootstrap import ensure_groups_config
from .routes import static, auth, admin, user, workflow_routes
from .utils.sfw_intercept.reactor_sfw_intercept import _load_reactor_module
from .utils.sfw_intercept.nsfw_guard import (
    should_block_image_for_current_user,
    set_latest_prompt_user,
)
from .utils.sfw_intercept.node_interceptor import install_node_interceptor
from .utils.comfy_user_bridge import (
    install_comfy_user_bridge,
    create_comfy_user_middleware,
)

import server

WEB_DIRECTORY = "./web"

# Export the public API for other extensions
try:
    from . import api
    __all__ = ["NODE_CLASS_MAPPINGS", "WEB_DIRECTORY", "api"]
except ImportError:
    __all__ = ["NODE_CLASS_MAPPINGS", "WEB_DIRECTORY"]

ensure_groups_config()


# --- WORKFLOW + GLOBAL SFW INTERCEPTION MIDDLEWARE ---
@web.middleware
async def workflow_interceptor_middleware(request, handler):
    path = request.path
    method = request.method
    

    # 1. Dispatcher
    response = await workflow_routes.middleware_dispatch(request)
    if isinstance(response, web.StreamResponse):
        return response

    # 2. User Resolution (jwt_auth sets request["user"] to username string)
    username = None
    try:
        raw_user = request.get("user") if hasattr(request, "get") else None
        if isinstance(raw_user, dict):
            username = raw_user.get("username")
        elif isinstance(raw_user, str) and raw_user.strip():
            username = raw_user.strip()
        if not username:
            username = workflow_routes.get_current_user(request)
    except Exception:
        username = None

    # Store for *HTTP* context: fall back to 'guest' only for HTTP-only checks
    current_username_var.set(username or "guest")

    # --- USER CAPTURE FOR WORKER THREAD ---
    if "prompt" in path and method in ("POST", "PUT"):
        # Let nsfw_guard handle defaulting/guest logic.
        set_latest_prompt_user(username)
        print(f"[Usgromana::Middleware] PROMPT CAPTURE path={path} user={username!r}")

    # --- NSFW only (/view, /static_gallery): independent of assets visibility ---
    if path == "/view" and method == "GET":
        from .utils.media_paths import resolve_output_file_path

        q = request.rel_url.query
        filename = q.get("filename") or q.get("file") or q.get("name")
        img_type = q.get("type", "output")
        subfolder = q.get("subfolder") or ""

        if filename and img_type == "output":
            img_path = resolve_output_file_path(filename, subfolder)
            if img_path and should_block_image_for_current_user(img_path):
                return web.Response(status=403, text="NSFW Blocked")
        elif filename and img_type == "temp":
            from .utils.media_paths import global_temp_directory

            img_path = os.path.normpath(
                os.path.join(global_temp_directory(), subfolder, filename)
                if subfolder
                else os.path.join(global_temp_directory(), filename)
            )
            if os.path.isfile(img_path) and should_block_image_for_current_user(img_path):
                return web.Response(status=403, text="NSFW Blocked")

    # --- Case B: /static_gallery ---
    if path.startswith("/static_gallery/") and method == "GET":
        from .utils.media_paths import resolve_static_gallery_path

        rel = path[len("/static_gallery/") :].lstrip("/\\")
        img_path = resolve_static_gallery_path(rel)
        if img_path and should_block_image_for_current_user(img_path):
            return web.Response(status=403, text="NSFW Blocked")

    return await handler(request)

# ---------------- Core middlewares ----------------
if FORCE_HTTPS:
    from .utils.force_https import create_https_middleware
    app.middlewares.append(create_https_middleware(MATCH_HEADERS))

app.middlewares.append(ip_filter.create_ip_filter_middleware())
app.middlewares.append(sanitizer.create_sanitizer_middleware())
app.middlewares.append(
    timeout.create_time_out_middleware(
        limited=("/login", "/register", "/generate_token")
    )
)

# IMPORTANT: run JWT auth BEFORE we try to read request.user in workflow_interceptor
app.middlewares.append(jwt_auth.create_jwt_middleware(
    public=("/login", "/logout", "/register", "/generate_token"),
    public_prefixes=("/usgromana", "/usgromana-gallery", "/assets", "/static"),
))

# Now that jwt_auth can populate request.user, we can safely
# resolve usernames inside workflow_interceptor_middleware.
app.middlewares.append(workflow_interceptor_middleware)

if SEPARATE_USERS:
    app.middlewares.append(access_control.create_folder_access_control_middleware())
    access_control.patch_folder_paths()
    access_control.patch_prompt_queue()
    install_comfy_user_bridge()
    app.middlewares.append(create_comfy_user_middleware())

app.middlewares.append(access_control.create_usgromana_middleware())
watcher.register(app)

install_node_interceptor()

# Ensure routes are added to the app
# In ComfyUI, instance.routes should be automatically added by PromptServer,
# but we'll explicitly add them to ensure they're registered
from .globals import routes
try:
    # Check if routes are already in the app
    routes_in_app = any(r._resource is routes for r in app.router.routes() if hasattr(r, '_resource'))
    if not routes_in_app:
        app.add_routes(routes)
except Exception:
    # Try to add anyway - might work even if check fails
    try:
        app.add_routes(routes)
    except Exception:
        pass  # ComfyUI may handle route registration automatically

print("------------------------------------------")
print("[Usgromana] Security System Initialized.")
print("[Usgromana] Workflow Storage Interceptor Active.")
print("------------------------------------------")
# --- END OF FILE __init__.py ---

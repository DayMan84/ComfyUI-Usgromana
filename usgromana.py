from aiohttp import web
from server import PromptServer
from .globals import (
    app, routes, ip_filter, sanitizer, timeout, jwt_auth, access_control,
    GROUPS_CONFIG_FILE, users_db
)
from .utils.watcher import watcher
from .utils.bootstrap import ensure_groups_config

# --- Import Routes to register them ---
# Just importing them is enough because they use the @routes decorator from globals
import usgromana.routes.auth
import usgromana.routes.admin
import usgromana.routes.user

# --- Bootstrap ---
ensure_groups_config()

# --- Static Files ---
# Define your directories here or in globals
CSS_DIR = "..." 
JS_DIR = "..."
ASSETS_DIR = "..."

app.add_routes([
    web.static("/usgromana/css", CSS_DIR),
    web.static("/usgromana/js", JS_DIR),
    web.static("/usgromana/assets", ASSETS_DIR),
])

# --- Middleware Registration ---
# Add your conditional checks (FORCE_HTTPS, etc) here

app.middlewares.append(ip_filter.create_ip_filter_middleware())
app.middlewares.append(sanitizer.create_sanitizer_middleware())
app.middlewares.append(timeout.create_time_out_middleware(limited=("/login", "/register")))
app.middlewares.append(jwt_auth.create_jwt_middleware(public=("/login", "/logout", "/register"), public_prefixes=("/usgromana", "/assets")))

# Folder/Queue Access Control
app.middlewares.append(access_control.create_folder_access_control_middleware())
access_control.patch_folder_paths()
access_control.patch_prompt_queue()

# Main Permission Middleware
app.middlewares.append(access_control.create_usgromana_middleware())

# Watcher
watcher.register(app)

print("[Usgromana] Initialized successfully.")
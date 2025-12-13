# --- START OF FILE routes/workflow_routes.py ---
import os
import json
import time
from aiohttp import web

from ..globals import jwt_auth, current_username_var, users_db
from ..utils import user_env
from ..utils.sfw_intercept.nsfw_guard import should_block_image_for_current_user
import folder_paths

# 1. Determine Paths
COMFY_ROOT = folder_paths.base_path

POTENTIAL_GLOBALS = [
    os.path.join(COMFY_ROOT, "user", "default", "workflows"),
    os.path.join(COMFY_ROOT, "user_data", "workflows"),
]


def get_current_user(request):
    """
    Extract username from JWT token in the request.
    Falls back to 'guest' on any error / no token.
    """
    token = jwt_auth.get_token_from_request(request)
    if not token:
        return "guest"
    try:
        payload = jwt_auth.decode_access_token(token)
        return payload.get("username", "guest")
    except Exception:
        return "guest"

def user_is_admin(username: str) -> bool:
    """
    Returns True if the given username is in the 'admin' group
    according to users_db. Handles both dict and tuple returns.
    Falls back safely to False on any error.
    """
    try:
        record = users_db.get_user(username)
        if not record:
            print(f"[Usgromana] user_is_admin: no record for {username!r}")
            return False

        # users_db.get_user(...) might return:
        # - a dict
        # - a tuple where one element is the dict (e.g. (user_dict, something))
        user_obj = None

        if isinstance(record, dict):
            user_obj = record
        elif isinstance(record, tuple):
            # Try to find the dict inside the tuple
            for item in record:
                if isinstance(item, dict):
                    user_obj = item
                    break

        if not user_obj:
            print(f"[Usgromana] user_is_admin: unexpected record type for {username!r}: {type(record)} -> {record!r}")
            return False

        groups = user_obj.get("groups") or user_obj.get("group") or []
        if isinstance(groups, str):
            groups = [groups]

        is_admin = any(str(g).lower() == "admin" for g in groups)
        print(f"[Usgromana] user_is_admin: {username!r} groups={groups!r} is_admin={is_admin}")
        return is_admin

    except Exception as e:
        print(f"[Usgromana] user_is_admin error for {username!r}: {e}")
        return False

# --- Helper: Sanitize Name ---
def sanitize_name(name: str | None) -> str | None:
    if not name:
        return None
    # Fix backslashes and remove ..
    clean = name.replace("\\", "/").strip()
    # Basic path traversal protection
    if ".." in clean or clean.startswith("/"):
        return None
    # Ensure json extension
    if not clean.lower().endswith(".json"):
        clean += ".json"
    return clean


# --- Helper: Get File Info ---
def get_file_info(root_dir: str, rel_path: str) -> dict:
    full_path = os.path.join(root_dir, rel_path)

    rel_norm = rel_path.replace("\\", "/")
    parts = rel_norm.split("/")
    filename = parts[-1]
    subfolder = "/".join(parts[:-1]) if len(parts) > 1 else ""

    ext = "json"
    if "." in filename:
        ext = filename.rsplit(".", 1)[1]

    stats = {}
    try:
        st = os.stat(full_path)
        stats["created"] = st.st_ctime
        stats["modified"] = st.st_mtime
        stats["size"] = st.st_size
    except Exception:
        stats["created"] = time.time()
        stats["modified"] = time.time()
        stats["size"] = 0

    base_info = {
        "name": filename,
        "filename": filename,
        "file": rel_norm,
        "id": rel_norm,
        "path": rel_norm,
        "subfolder": subfolder,
        "ext": ext,
        "extension": ext,
        "type": "file",
        "format": "json",
        "created": stats["created"],
        "modified": stats["modified"],
        "size": stats["size"],
        "writable": True,
    }

    # Some UI expects nested data
    base_info["data"] = base_info.copy()
    return base_info


# --- 1. LIST (GET) ---
async def list_workflows(request, full_info: bool = False):
    user = get_current_user(request)
    files_map: dict[str, dict] = {}

    # Global
    for global_dir in POTENTIAL_GLOBALS:
        if os.path.exists(global_dir):
            for root, _, files in os.walk(global_dir):
                for f in files:
                    if f.endswith(".json"):
                        rel = os.path.relpath(os.path.join(root, f), global_dir)
                        key = rel.replace("\\", "/")
                        files_map[key] = get_file_info(global_dir, rel)

    # Private
    if user != "guest":
        user_dir = user_env.get_user_workflow_dir(user)
        if os.path.exists(user_dir):
            for root, _, files in os.walk(user_dir):
                for f in files:
                    if f.endswith(".json"):
                        rel = os.path.relpath(os.path.join(root, f), user_dir)
                        key = rel.replace("\\", "/")
                        files_map[key] = get_file_info(user_dir, rel)
        else:
            os.makedirs(user_dir, exist_ok=True)

    return web.json_response(list(files_map.values()))


# --- 2. SAVE (POST) ---
async def save_workflow(request, name_override: str | None = None):
    user = get_current_user(request)

    try:
        try:
            data = await request.json()
        except Exception:
            return web.Response(status=400, text="Invalid JSON")

        name = name_override
        if not name:
            name = request.query.get("file", "")
        if not name:
            name = request.query.get("name", "")
        if not name:
            name = data.get("name", "")
        if not name:
            name = "untitled.json"

        clean_name = sanitize_name(name)
        if not clean_name:
            return web.Response(status=400, text="Invalid filename")

        user_dir = user_env.get_user_workflow_dir(user)
        file_path = os.path.join(user_dir, clean_name)

        print(f"[Usgromana] User '{user}' saving workflow: {clean_name}")

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Strip metadata fields that come from UI listing
        meta_keys = [
            "created",
            "modified",
            "size",
            "type",
            "ext",
            "extension",
            "filename",
            "file",
            "path",
            "subfolder",
            "data",
        ]
        for k in meta_keys:
            if k in data:
                del data[k]

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # Return fresh file info so UI can update list
        saved_info = get_file_info(user_dir, clean_name)
        return web.json_response(saved_info)

    except Exception as e:
        print(f"[Usgromana] Save Error: {e}")
        return web.Response(status=500, text=str(e))


# --- 3. LOAD CONTENT (GET) ---
async def get_workflow_content(request, name: str):
    user = get_current_user(request)

    clean_name = sanitize_name(name)
    if not clean_name:
        return web.Response(status=404)

    # First: user-specific workflow
    user_dir = user_env.get_user_workflow_dir(user)
    user_path = os.path.join(user_dir, clean_name)
    if os.path.exists(user_path) and os.path.isfile(user_path):
        return web.FileResponse(user_path)

    # Then: global workflows
    for global_dir in POTENTIAL_GLOBALS:
        global_path = os.path.join(global_dir, clean_name)
        if os.path.exists(global_path) and os.path.isfile(global_path):
            return web.FileResponse(global_path)

    return web.Response(status=404, text="Workflow not found")


# --- 4. DELETE (DELETE) ---
async def delete_workflow(request, name: str | None):
    user = get_current_user(request)

    # Resolve filename from query if not passed explicitly
    if not name:
        name = request.query.get("file", "")
    if not name:
        name = request.query.get("name", "")

    clean_name = sanitize_name(name)
    if not clean_name:
        return web.Response(status=400, text="Invalid filename")

    # --- 1. Try deleting from the user's own folder ---
    user_dir = user_env.get_user_workflow_dir(user)
    user_path = os.path.join(user_dir, clean_name)

    if os.path.exists(user_path):
        os.remove(user_path)
        print(f"[Usgromana] User '{user}' deleted workflow: {clean_name}")
        # Match core ComfyUI: DELETE /userdata/{file} -> 204 No Content
        return web.Response(status=204)

    # --- 2. Try deleting from global/default folders ---
    is_admin = user_is_admin(user)
    print(f"[Usgromana] delete_workflow user={user!r}, is_admin={is_admin}, name={clean_name!r}")

    for global_dir in POTENTIAL_GLOBALS:
        global_path = os.path.join(global_dir, clean_name)
        if os.path.exists(global_path):
            if is_admin:
                os.remove(global_path)
                print(
                    f"[Usgromana] ADMIN '{user}' deleted GLOBAL workflow: "
                    f"{clean_name} ({global_path})"
                )
                return web.Response(status=204)
            else:
                # Found in global, but user is not allowed to delete it
                return web.Response(status=403, text="Cannot delete global workflows")

    # --- 3. Not found anywhere ---
    return web.Response(status=404, text="Workflow not found")

# --- 5. DISPATCHER / MIDDLEWARE ---
async def middleware_dispatch(request):
    """
    Intercepts workflow-related API calls and /prompt and /view.

    - For workflow paths, routes to list/save/load/delete.
    - For /prompt, tags the current username in current_username_var
      so other parts of Usgromana know which user is executing the prompt.
    - For /view, applies global NSFW enforcement for SFW users
      using utils.nsfw_guard.
    """
    path = request.path
    method = request.method
    
    # Don't intercept usgromana-gallery routes
    if path.startswith("/usgromana-gallery"):
        return None

    # Optional bypass
    if request.query.get("bypass") == "true":
        return None

    # --- Global NSFW enforcement on /view ---
    if path == "/view" and method == "GET":
        username = get_current_user(request)
        current_username_var.set(username)
        print(f"[Usgromana] /view requested by user: {username!r}")

        q = request.rel_url.query
        filename = q.get("filename") or q.get("file") or q.get("name")
        img_type = q.get("type", "output")

        # Only guard standard output images for now
        if filename and img_type == "output":
            out_dir = folder_paths.get_output_directory()
            img_path = os.path.join(out_dir, filename)

            if os.path.isfile(img_path):
                try:
                    if should_block_image_for_current_user(img_path):
                        # Hard global block for this user
                        print(f"[Usgromana::NSFWGuard] Blocking NSFW image for user={username!r}: {img_path}")
                        return web.Response(status=403, text="NSFW content blocked for this user.")
                except Exception as e:
                    print(f"[Usgromana::NSFWGuard] Error while checking {img_path}: {e}")

        # Fall through to normal handler if not blocked
        return None

    # --- Workflow user-data endpoints ---
    if path.endswith("/api/userdata") and request.query.get("dir") == "workflows":
        if method == "GET":
            return await list_workflows(request, full_info=True)
        elif method == "POST":
            return await save_workflow(request)
        elif method == "DELETE":
            return await delete_workflow(request, name=None)
        return None

    if "userdata/workflows" in path:
        parts = path.split("/workflows")
        suffix = parts[1] if len(parts) > 1 else ""
        if suffix.startswith("/"):
            suffix = suffix[1:]

        if method == "GET":
            if suffix:
                return await get_workflow_content(request, suffix)
            else:
                return await list_workflows(request, full_info=True)
        elif method == "POST":
            return await save_workflow(request, name_override=suffix)
        elif method == "DELETE":
            return await delete_workflow(request, name=suffix)

    # --- Intercept prompt execution to tag current username for SFW logic ---
    if path == "/prompt" and method in ("POST", "PUT"):
        username = get_current_user(request)
        current_username_var.set(username)
        print(f"[Usgromana] /prompt tagged for user: {username!r}")
        # Do not block; let the normal ComfyUI /prompt handler run
        return None

    return None

# --- END OF FILE routes/workflow_routes.py ---

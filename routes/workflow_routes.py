# --- START OF FILE routes/workflow_routes.py ---
import os
import json
import time
from aiohttp import web
from ..globals import jwt_auth
from ..utils import user_env
import folder_paths

# 1. Determine Paths
COMFY_ROOT = folder_paths.base_path

POTENTIAL_GLOBALS = [
    os.path.join(COMFY_ROOT, "user", "default", "workflows"),
    os.path.join(COMFY_ROOT, "user_data", "workflows")
]

def get_current_user(request):
    token = jwt_auth.get_token_from_request(request)
    if not token: return "guest"
    try:
        payload = jwt_auth.decode_access_token(token)
        return payload.get("username", "guest")
    except:
        return "guest"

# --- Helper: Sanitize Name ---
def sanitize_name(name):
    if not name: return None
    # Fix backslashes and remove ..
    clean = name.replace("\\", "/").strip()
    # Basic path traversal protection
    if ".." in clean or clean.startswith("/"): return None
    # Ensure json extension
    if not clean.lower().endswith(".json"): clean += ".json"
    return clean

# --- Helper: Get File Info ---
def get_file_info(root_dir, rel_path):
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
    except:
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
        "writable": True
    }
    
    # Critical: Nested data for some UI versions
    base_info["data"] = base_info.copy()
    return base_info

# --- 1. LIST (GET) ---
async def list_workflows(request, full_info=False):
    user = get_current_user(request)
    files_map = {} 

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
async def save_workflow(request, name_override=None):
    user = get_current_user(request)
    
    try:
        try:
            data = await request.json()
        except:
            return web.Response(status=400, text="Invalid JSON")

        name = name_override
        if not name: name = request.query.get("file", "")
        if not name: name = request.query.get("name", "")
        if not name: name = data.get("name", "")
        if not name: name = "untitled.json"
        
        clean_name = sanitize_name(name)
        if not clean_name:
             return web.Response(status=400, text="Invalid filename")

        user_dir = user_env.get_user_workflow_dir(user)
        file_path = os.path.join(user_dir, clean_name)
        
        print(f"[Usgromana] User '{user}' saving: {clean_name}")
        
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Strip metadata
        meta_keys = ["created", "modified", "size", "type", "ext", "extension", "filename", "file", "path", "subfolder", "data"]
        for k in meta_keys:
            if k in data: del data[k]

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        # FIX: Return complete file metadata so UI updates list
        saved_info = get_file_info(user_dir, clean_name)
        return web.json_response(saved_info)

    except Exception as e:
        print(f"[Usgromana] Save Error: {e}")
        return web.Response(status=500, text=str(e))

# --- 3. LOAD CONTENT (GET) ---
async def get_workflow_content(request, name):
    user = get_current_user(request)
    
    clean_name = sanitize_name(name)
    if not clean_name: return web.Response(status=404)
    
    user_dir = user_env.get_user_workflow_dir(user)
    user_path = os.path.join(user_dir, clean_name)
    if os.path.exists(user_path) and os.path.isfile(user_path):
        return web.FileResponse(user_path)
        
    for global_dir in POTENTIAL_GLOBALS:
        global_path = os.path.join(global_dir, clean_name)
        if os.path.exists(global_path) and os.path.isfile(global_path):
            return web.FileResponse(global_path)
        
    return web.Response(status=404, text="Workflow not found")

# --- 4. DELETE (DELETE) ---
async def delete_workflow(request, name):
    user = get_current_user(request)
    
    if not name: name = request.query.get("file", "")
    if not name: name = request.query.get("name", "")

    clean_name = sanitize_name(name)
    if not clean_name: return web.Response(status=400)

    user_dir = user_env.get_user_workflow_dir(user)
    user_path = os.path.join(user_dir, clean_name)
    
    if os.path.exists(user_path):
        os.remove(user_path)
        print(f"[Usgromana] User '{user}' deleted: {clean_name}")
        # FIX: Return empty JSON object {} to satisfy JSON parsers while indicating success
        return web.json_response({})
        
    for global_dir in POTENTIAL_GLOBALS:
        if os.path.exists(os.path.join(global_dir, clean_name)):
            return web.Response(status=403, text="Cannot delete global workflows")
        
    return web.Response(status=404)

# --- 5. DISPATCHER ---
async def middleware_dispatch(request):
    path = request.path
    method = request.method
    
    if request.query.get("bypass") == "true": return None 

    # Generic API
    if path.endswith("/api/userdata") and request.query.get("dir") == "workflows":
        if method == "GET":
             return await list_workflows(request, full_info=True)
        elif method == "POST":
             return await save_workflow(request)
        elif method == "DELETE":
             return await delete_workflow(request, name=None) 
        return None

    # Specific API
    if "userdata/workflows" in path:
        parts = path.split("/workflows")
        suffix = parts[1] if len(parts) > 1 else ""
        if suffix.startswith("/"): suffix = suffix[1:]

        if method == "GET":
             if suffix: return await get_workflow_content(request, suffix)
             else: return await list_workflows(request, full_info=True)
        elif method == "POST":
             return await save_workflow(request, name_override=suffix)
        elif method == "DELETE":
             return await delete_workflow(request, name=suffix)

    return None
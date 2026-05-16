# --- START OF FILE utils/access_control.py ---
import os
import json
import heapq
import copy
import contextvars
from aiohttp import web
import folder_paths
from server import PromptServer
from execution import PromptQueue, MAXIMUM_HISTORY_SIZE
from .users_db import UsersDB

# Map Permission Keys -> URL Paths to Block
EXTENSION_BLOCK_MAP = {
    "settings_itools": ["/extensions/ComfyUI-iTools", "/api/itools"],
    "settings_crystools": ["/extensions/ComfyUI-Crystools", "/api/crystools"],
    "settings_rgthree": ["/extensions/rgthree-comfy", "/api/rgthree", "/rgthree"],
    "settings_gallery": ["/extensions/comfyui-gallery", "/api/gallery"],
    "can_access_manager": ["/extensions/comfyui-manager", "/api/manager", "/manager"],
    "can_manage_extensions": [
        "/Comfy.Extension",
        "/api/settings/Comfy/Extension",
        "/api/settings/Comfy/Extension/enable",
        "/api/settings/Comfy/Extension/Disabled",
        "/api/extensions/apply",
        "/extensions"
    ],
    "can_modify_workflows": [
        "/api/userdata/workflows:",
        "/api/userdata/workflows/save",
        "/api/userdata/workflows/export"
    ]
}


def _usgromana_meta_from_queue_entry(entry):
    """Split Usgromana ``{user_id}`` tail from a queue heap entry."""
    if isinstance(entry, tuple) and entry and isinstance(entry[-1], dict):
        if "user_id" in entry[-1]:
            return entry[-1], entry[:-1]
    return {}, entry


def sanitize_prompt_tuple_for_api(prompt_tuple):
    """
    ComfyUI ``/api/jobs`` expects history prompt tuples with 5 elements
    (priority, prompt_id, prompt, extra_data, outputs_to_execute).
    Newer Comfy adds ``sensitive`` at index 5; strip it before persisting history.
    """
    if not isinstance(prompt_tuple, tuple):
        return prompt_tuple
    _, body = _usgromana_meta_from_queue_entry(prompt_tuple)
    if len(body) > 5:
        return body[:5]
    return body


class AccessControl:
    def __init__(self, users_db: UsersDB, server: PromptServer, groups_config_file: str):
        self.users_db = users_db
        self.server = server
        self.groups_config_file = groups_config_file

        self._current_user = contextvars.ContextVar("user_id", default=None)
        self.__current_user_id = None
        self.__get_output_directory = folder_paths.get_output_directory
        self.__get_temp_directory = folder_paths.get_temp_directory
        self.__get_input_directory = folder_paths.get_input_directory
        self.__prompt_queue = self.server.prompt_queue
        self.__prompt_queue_put = self.__prompt_queue.put

    def _load_group_config(self):
        if not os.path.exists(self.groups_config_file):
            return {}
        try:
            with open(self.groups_config_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def _get_user_role_and_permissions(self, request):
        token = None
        if "jwt_token" in request.cookies:
            token = request.cookies.get("jwt_token")
        if not token and "Authorization" in request.headers:
            parts = request.headers.get("Authorization", "").split(" ")
            if len(parts) == 2: token = parts[1]

        if not token: return "guest", {}, None

        try:
            import jwt
            # Decode without verification here just to get username for role lookup
            # The actual security check happens in JWTAuth middleware
            payload = jwt.decode(token, options={"verify_signature": False})
            username = payload.get("username")

            _, user_rec = self.users_db.get_user(username)
            if not user_rec: return "guest", {}, None

            groups = [g.lower() for g in user_rec.get("groups", [])]
            role = groups[0] if groups else "user"
            cfg = self._load_group_config()
            perms = cfg.get(role, {})
            return role, perms, username
        except Exception:
            return "guest", {}, None

    def create_usgromana_middleware(self):
        @web.middleware
        async def middleware(request: web.Request, handler):
            path = request.path
            
            # 1. Public Whitelist
            if (path.startswith(("/login", "/register", "/logout", "/usgromana", "/usgromana-gallery", "/static", "/favicon", "/ws", "/assets")) or path == "/"):
                return await handler(request)
            
            # 2. Core Extensions
            if path.startswith(("/extensions/core", "/extensions/ComfyUI-Usgromana", "/extensions/Usgromana")):
                return await handler(request)

            # 3. Resolve User
            role, perms, username = self._get_user_role_and_permissions(request)

            # 4. Check Permissions
            is_queue = path.startswith(("/prompt", "/api/prompt", "/api/queue", "/queue"))
            is_upload = path.startswith(("/upload", "/api/upload"))
            is_userdata_workflow = path.startswith(("/api/userdata/workflows", "/api/userdata/workflows:"))

            if is_queue and perms.get("can_run") is False:
                return web.json_response({"error": "Usgromana: Execution Denied"}, status=403)

            if is_upload and perms.get("can_upload") is False:
                return web.json_response({"error": "Usgromana: Upload Denied"}, status=403)

            if is_userdata_workflow and request.method in ("POST", "PUT", "DELETE", "PATCH"):
                can_modify = perms.get("can_modify_workflows")
                if can_modify is None: can_modify = (role != "guest")
                if role == "admin": can_modify = True

                if not can_modify:
                    return web.json_response({"error": "Usgromana: Workflow Denied", "code": "WORKFLOW_DENIED", "role": role}, status=403)

            for perm_key, blocked_paths in EXTENSION_BLOCK_MAP.items():
                allow = perms.get(perm_key)
                if allow is None: allow = (role != "guest")
                if role == "admin": allow = True
                if allow is False:
                    for blocked_prefix in blocked_paths:
                        if path.lower().startswith(blocked_prefix.lower()):
                            return web.Response(status=403, text="Usgromana: Access Denied")

            if not is_queue and not is_upload and path.startswith("/api/"):
                if perms.get("can_access_api") is False:
                    return web.json_response({"error": "Usgromana: API Denied"}, status=403)

            return await handler(request)
        return middleware

    # --- Folder & User Context Methods ---

    def set_current_user_id(self, user_id: str, set_fallback=False):
        self._current_user.set(user_id)
        if set_fallback: self.__current_user_id = user_id
    
    def get_current_user_id(self):
        return self._current_user.get() or self.__current_user_id

    def _resolved_directory_user_id(self) -> str | None:
        """User id for per-user folder roots, or None when no request context (e.g. startup asset scan)."""
        uid = self.get_current_user_id()
        return uid if uid else None

    def get_user_output_directory(self):
        base = self.__get_output_directory()
        uid = self._resolved_directory_user_id()
        if not uid:
            return base
        path = os.path.join(base, uid)
        os.makedirs(path, exist_ok=True)
        return path

    def get_user_temp_directory(self):
        base = self.__get_temp_directory()
        uid = self._resolved_directory_user_id()
        if not uid:
            return base
        path = os.path.join(base, uid)
        os.makedirs(path, exist_ok=True)
        return path

    def get_user_input_directory(self):
        base = self.__get_input_directory()
        uid = self._resolved_directory_user_id()
        if not uid:
            return base
        path = os.path.join(base, uid)
        os.makedirs(path, exist_ok=True)
        return path

    def get_user_storage_prefixes(self, user_id: str | None = None) -> list[str]:
        """Absolute paths for a user's isolated output/input/temp folders."""
        uid = user_id or self._resolved_directory_user_id()
        if not uid:
            return []
        prefixes = []
        for base in (
            self.__get_output_directory(),
            self.__get_input_directory(),
            self.__get_temp_directory(),
        ):
            path = os.path.join(base, uid)
            os.makedirs(path, exist_ok=True)
            prefixes.append(os.path.abspath(path))
        return prefixes

    def add_user_specific_folder_paths(self, json_data):
        user_id = self._resolved_directory_user_id()
        if not user_id:
            return json_data
        if isinstance(json_data, dict):
            for k, v in json_data.items():
                if k == "filename_prefix" and isinstance(v, str):
                    # input/output/temp roots are already per-user; do not nest user_id again.
                    clean = v.replace("\\", "/").strip("/")
                    if clean.startswith(f"{user_id}/"):
                        json_data[k] = clean
                    else:
                        json_data[k] = clean
                else:
                    self.add_user_specific_folder_paths(v)
        elif isinstance(json_data, list):
            for item in json_data:
                self.add_user_specific_folder_paths(item)
        return json_data

    def patch_folder_paths(self):
        # Match ComfyUI Assets view: each user sees their own input/output/temp roots.
        folder_paths.get_output_directory = self.get_user_output_directory
        folder_paths.get_temp_directory = self.get_user_temp_directory
        folder_paths.get_input_directory = self.get_user_input_directory
        self.server.add_on_prompt_handler(self.add_user_specific_folder_paths)

    # --- MISSING METHOD RESTORED HERE ---
    def create_folder_access_control_middleware(self):
        folder_paths_check = (
            self.__get_output_directory(),
            self.__get_temp_directory(),
            self.__get_input_directory(),
        )

        @web.middleware
        async def middleware(request: web.Request, handler):
            if not request.path.startswith(folder_paths_check):
                return await handler(request)
            # Future expansion: Check permissions for specific file access here
            return await handler(request)

        return middleware

    # --- Queue Patching ---

    def patch_prompt_queue(self):
        self.__prompt_queue.put = self.user_queue_put
        self.__prompt_queue.get = self.user_queue_get
        self.__prompt_queue.task_done = self.user_queue_task_done
        self.__prompt_queue.get_current_queue = self.user_queue_get_current_queue
        self.__prompt_queue.wipe_queue = self.user_queue_wipe_queue
        self.__prompt_queue.delete_queue_item = self.user_queue_delete_queue_item
        self.__prompt_queue.get_history = self.user_queue_get_history
        self.__prompt_queue.wipe_history = self.user_queue_wipe_history

    def user_queue_put(self, item):
        current_user_id = self.get_current_user_id()
        _, user_rec = self.users_db.get_user(current_user_id)

        if user_rec:
            if os.path.exists(self.groups_config_file):
                try:
                    with open(self.groups_config_file, 'r') as f:
                        cfg = json.load(f)
                    groups = user_rec.get("groups", ["user"])
                    role = groups[0] if groups else "user"
                    perms = cfg.get(role, {})
                    if perms.get("can_run") is False:
                        print(f"[AccessControl] Blocked execution for {current_user_id}")
                        return
                except Exception:
                    pass

        if isinstance(item, tuple):
            new_item = (*item, {"user_id": current_user_id})
        else:
            new_item = (item, {"user_id": current_user_id})
        self.__prompt_queue_put(new_item)

    def user_queue_get(self, timeout=None):
        with self.__prompt_queue.not_empty:
            while not self.__prompt_queue.queue:
                self.__prompt_queue.not_empty.wait(timeout=timeout)
                if timeout and not self.__prompt_queue.queue:
                    return None
            entry = heapq.heappop(self.__prompt_queue.queue)
            task_id = self.__prompt_queue.task_counter
            self.__prompt_queue.currently_running[task_id] = entry
            self.__prompt_queue.task_counter += 1
            self.server.queue_updated()
            return (entry, task_id)

    def user_queue_task_done(self, item_id, history_result, **kwargs):
        process_item = kwargs.get("process_item")
        status = kwargs.get("status")
        with self.__prompt_queue.mutex:
            item = self.__prompt_queue.currently_running.pop(item_id)
            while len(self.__prompt_queue.history) > MAXIMUM_HISTORY_SIZE:
                self.__prompt_queue.history.pop(next(iter(self.__prompt_queue.history)))

            meta, prompt_body = _usgromana_meta_from_queue_entry(item)
            if process_item is not None:
                prompt_stored = process_item(prompt_body)
            else:
                prompt_stored = sanitize_prompt_tuple_for_api(prompt_body)

            if status is not None and hasattr(status, "_asdict"):
                status_dict = copy.deepcopy(status._asdict())
            else:
                status_dict = {
                    "completed": kwargs.get("completed"),
                    "messages": kwargs.get("messages"),
                }

            prompt_id = prompt_stored[1]
            self.__prompt_queue.history[prompt_id] = {
                "prompt": prompt_stored,
                "outputs": {},
                "status": status_dict,
                "user_id": meta.get("user_id"),
            }
            if history_result:
                self.__prompt_queue.history[prompt_id].update(history_result)
                prompt_user = meta.get("user_id")
                if prompt_user:
                    try:
                        self.set_current_user_id(prompt_user, set_fallback=True)
                        from .sfw_intercept.nsfw_guard import (
                            tag_output_images_from_history,
                        )

                        tag_output_images_from_history(history_result)
                        from .comfy_user_bridge import register_outputs_from_history

                        register_outputs_from_history(history_result, prompt_user)
                    except Exception as e:
                        print(f"[Usgromana] post-prompt hooks: {e}")
            self.server.queue_updated()

    def user_queue_get_current_queue(self):
        def unwrap(entry):
            _, body = _usgromana_meta_from_queue_entry(entry)
            return sanitize_prompt_tuple_for_api(body)

        current_user = self.get_current_user_id()
        with self.__prompt_queue.mutex:
            running = []
            pending = []
            for item in self.__prompt_queue.currently_running.values():
                meta = item[-1] if isinstance(item[-1], dict) else None
                if not meta or meta.get("user_id") != current_user: continue
                running.append(unwrap(item))
            for item in self.__prompt_queue.queue:
                meta = item[-1] if isinstance(item[-1], dict) else None
                if not meta or meta.get("user_id") != current_user: continue
                pending.append(unwrap(item))
            return (running, copy.deepcopy(pending))

    def user_queue_wipe_queue(self):
        with self.__prompt_queue.mutex:
            current_user = self.get_current_user_id()
            self.__prompt_queue.queue = [
                i for i in self.__prompt_queue.queue
                if not (isinstance(i[-1], dict) and i[-1].get("user_id") == current_user)
            ]
            self.server.queue_updated()

    def user_queue_delete_queue_item(self, func):
        def unwrap(entry):
            _, body = _usgromana_meta_from_queue_entry(entry)
            return sanitize_prompt_tuple_for_api(body)

        with self.__prompt_queue.mutex:
            for i, item in enumerate(self.__prompt_queue.queue):
                meta = item[-1] if isinstance(item[-1], dict) else None
                if meta and meta.get("user_id") == self.get_current_user_id() and func(unwrap(item)):
                    self.__prompt_queue.queue.pop(i)
                    heapq.heapify(self.__prompt_queue.queue)
                    self.server.queue_updated()
                    return True
        return False

    def user_queue_get_history(self, prompt_id=None, max_items=None, offset=-1):
        with self.__prompt_queue.mutex:
            user = self.get_current_user_id()
            filtered = {
                k: v for k, v in self.__prompt_queue.history.items()
                if v.get("user_id") == user
            }
            if prompt_id:
                if prompt_id not in filtered:
                    return {}
                entry = dict(filtered[prompt_id])
                if "prompt" in entry:
                    entry["prompt"] = sanitize_prompt_tuple_for_api(entry["prompt"])
                return {prompt_id: entry}
            keys = list(filtered.keys())
            if offset < 0:
                offset = max(0, len(keys) - max_items) if max_items else 0
            result = {}
            for k in keys[offset:]:
                entry = dict(filtered[k])
                if "prompt" in entry:
                    entry["prompt"] = sanitize_prompt_tuple_for_api(entry["prompt"])
                result[k] = entry
                if max_items and len(result) >= max_items:
                    break
            return result

    def user_queue_wipe_history(self):
        with self.__prompt_queue.mutex:
            u = self.get_current_user_id()
            self.__prompt_queue.history = {
                k: v for k, v in self.__prompt_queue.history.items()
                if v.get("user_id") != u
            }

# --- START OF FILE utils/access_control.py ---
import os
import re
import json
import heapq
import copy
import contextvars
from contextlib import contextmanager
from aiohttp import web
import folder_paths
from server import PromptServer
from execution import PromptQueue, MAXIMUM_HISTORY_SIZE
from .users_db import UsersDB

# Usgromana user ids are UUIDs (see routes/auth.py). A cached output_dir that
# still points at output/<that id> must be re-based when the executing user changes.
_USER_ID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

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
        # Prompt worker / helper threads. HTTP handlers must not overwrite this
        # by polling /api/jobs; get_current_user_id() prefers it over the global fallback.
        self._executing_user_id = None
        # Context-local replacement for process-wide folder_paths getter swaps.
        self._directory_override = contextvars.ContextVar(
            "usgromana_directory_override", default=None
        )
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

    def _bind_executing_user(self, user_id: str) -> None:
        """Pin the dequeued prompt's owner for the worker thread and its helpers.

        ``set_current_user_id(..., set_fallback=True)`` runs on every authenticated
        request, including other users' Generated-tab polling. The prompt worker
        has no request context, so it used to follow that process-wide fallback.
        """
        if not user_id:
            return
        self._executing_user_id = user_id
        self._current_user.set(user_id)

    def get_current_user_id(self):
        current = self._current_user.get()
        if current:
            return current
        if self._executing_user_id:
            return self._executing_user_id
        return self.__current_user_id

    def push_directory_override(
        self,
        *,
        output=None,
        input_directory=None,
        temp=None,
    ):
        """Context-local directory roots. Values may be path strings or callables.

        Returns a token for ``pop_directory_override``. Other threads, including
        the prompt worker, do not see this override.
        """
        parent = self._directory_override.get()
        state = dict(parent) if parent else {}
        if output is not None:
            state["output"] = output
        if input_directory is not None:
            state["input"] = input_directory
        if temp is not None:
            state["temp"] = temp
        return self._directory_override.set(state)

    def pop_directory_override(self, token) -> None:
        self._directory_override.reset(token)

    @contextmanager
    def directory_override(self, *, output=None, input_directory=None, temp=None):
        token = self.push_directory_override(
            output=output,
            input_directory=input_directory,
            temp=temp,
        )
        try:
            yield
        finally:
            self.pop_directory_override(token)

    def _resolve_directory_override(self, kind: str):
        state = self._directory_override.get()
        if not state or kind not in state:
            return None
        value = state[kind]
        return value() if callable(value) else value

    def _directory(self, kind: str, global_getter, per_user: bool):
        overridden = self._resolve_directory_override(kind)
        if overridden is not None:
            return overridden
        base = global_getter()
        if not per_user:
            return base
        uid = self._resolved_directory_user_id()
        if not uid:
            return base
        path = os.path.join(base, uid)
        os.makedirs(path, exist_ok=True)
        return path

    def _resolved_directory_user_id(self) -> str | None:
        """User id for per-user folder roots, or None when no request context (e.g. startup asset scan)."""
        uid = self.get_current_user_id()
        return uid if uid else None

    def get_user_output_directory(self):
        return self._directory("output", self.__get_output_directory, True)

    def get_user_temp_directory(self):
        return self._directory("temp", self.__get_temp_directory, True)

    def get_user_input_directory(self):
        return self._directory("input", self.__get_input_directory, True)

    @staticmethod
    def _is_under_directory(path: str, base: str) -> bool:
        path_n = os.path.normcase(os.path.abspath(path))
        base_n = os.path.normcase(os.path.abspath(base))
        return path_n == base_n or path_n.startswith(base_n + os.sep)

    def _is_user_path_segment(self, segment: str) -> bool:
        """True when a cached directory's first relative part is an isolated user folder."""
        if not segment:
            return False
        key = os.path.normcase(segment)
        known: set[str] = set()
        try:
            known.update(str(uid) for uid in self.users_db.users.keys())
        except Exception:
            pass
        for extra in (
            self._executing_user_id,
            self.__current_user_id,
            self._current_user.get(),
        ):
            if extra:
                known.add(str(extra))
        if any(os.path.normcase(uid) == key for uid in known):
            return True
        return _USER_ID_RE.match(segment) is not None

    def rebase_cached_directory(self, stored_path: str) -> str:
        """Map a directory captured at node init onto the executing user's root.

        ComfyUI constructs SaveImage / SaveLatent / PreviewImage once and keeps
        the instance in the node-object cache. ``output_dir`` is assigned in
        ``__init__`` and would otherwise keep pointing at the first user's folder.

        Paths under the global output, temp, or input roots are re-based onto
        the current user's matching root. A leading ``<user_id>`` segment is
        stripped so the folder is not nested twice. Absolute paths outside those
        roots (custom node destinations) are returned unchanged.
        """
        if not stored_path:
            return self.get_user_output_directory()

        stored = os.path.abspath(stored_path)
        candidates = (
            (self.__get_output_directory, self.get_user_output_directory),
            (self.__get_temp_directory, self.get_user_temp_directory),
            (self.__get_input_directory, self.get_user_input_directory),
        )
        best_base = None
        best_user_getter = None
        best_len = -1
        for global_getter, user_getter in candidates:
            try:
                base = os.path.abspath(global_getter())
            except Exception:
                continue
            if not self._is_under_directory(stored, base):
                continue
            if len(os.path.normcase(base)) > best_len:
                best_base = base
                best_user_getter = user_getter
                best_len = len(os.path.normcase(base))

        if best_base is None or best_user_getter is None:
            return stored

        rel = os.path.relpath(stored, best_base)
        if rel == ".":
            parts: list[str] = []
        else:
            parts = [
                part
                for part in rel.replace("\\", "/").split("/")
                if part not in ("", ".")
            ]
        if parts and self._is_user_path_segment(parts[0]):
            parts = parts[1:]

        current = os.path.abspath(best_user_getter())
        if not parts:
            return current
        return os.path.join(current, *parts)

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
        self._install_executor_user_switch_reset()
        self._install_dynamic_output_dirs()

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
            meta, _prompt_body = _usgromana_meta_from_queue_entry(entry)
            owner_id = meta.get("user_id")
            if owner_id:
                # Runs on the prompt worker thread, before PromptExecutor.execute.
                self._bind_executing_user(owner_id)
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

    def _reset_node_cache_if_user_changed(self, executor) -> None:
        """Drop cached node instances when the prompt owner changes.

        ComfyUI keys ``caches.objects`` by node id. The same workflow template
        therefore reuses SaveImage (and custom nodes) constructed for the
        previous user, including any directory captured in ``__init__``.
        """
        user_id = self._executing_user_id or self._current_user.get()
        if not user_id:
            return
        previous = getattr(executor, "_usgromana_cache_user_id", None)
        executor._usgromana_cache_user_id = user_id
        if previous is None or previous == user_id:
            return

        caches = getattr(executor, "caches", None)
        objects = None
        outputs = None
        if caches is not None:
            objects = getattr(caches, "objects", None)
            outputs = getattr(caches, "outputs", None)
            if isinstance(caches, dict):
                if objects is None:
                    objects = caches.get("objects")
                if outputs is None:
                    outputs = caches.get("outputs")
        if objects is None:
            objects = getattr(executor, "object_storage", None)
        self._clear_node_object_cache(objects)
        # The output cache also stores SaveImage UI filenames from the previous
        # user. Replaying that entry would point the next user at the other
        # user's files when the workflow inputs match.
        self._clear_node_object_cache(outputs)
        print(
            f"[Usgromana::Executor] user changed {previous!r} -> {user_id!r}: "
            "node object cache cleared"
        )

    @staticmethod
    def _clear_node_object_cache(cache_obj) -> None:
        if cache_obj is None:
            return
        if isinstance(cache_obj, dict):
            cache_obj.clear()
            return
        store = getattr(cache_obj, "cache", None)
        if isinstance(store, dict):
            store.clear()
        subcaches = getattr(cache_obj, "subcaches", None)
        if isinstance(subcaches, dict):
            subcaches.clear()
        for book_name in ("used_generation", "children", "timestamps"):
            book = getattr(cache_obj, book_name, None)
            if isinstance(book, dict):
                book.clear()

    def _install_executor_user_switch_reset(self) -> None:
        try:
            import execution
        except ImportError:
            print("[Usgromana] PromptExecutor patch skipped: execution module not found")
            return

        cls = getattr(execution, "PromptExecutor", None)
        if cls is None:
            print("[Usgromana] PromptExecutor patch skipped: PromptExecutor not found")
            return
        if getattr(cls, "_usgromana_executor_patched", False):
            return

        ac = self
        if hasattr(cls, "execute_async"):
            original = cls.execute_async

            async def execute_async(executor, *args, **kwargs):
                ac._reset_node_cache_if_user_changed(executor)
                return await original(executor, *args, **kwargs)

            cls.execute_async = execute_async
        elif hasattr(cls, "execute"):
            original = cls.execute

            def execute(executor, *args, **kwargs):
                ac._reset_node_cache_if_user_changed(executor)
                return original(executor, *args, **kwargs)

            cls.execute = execute
        else:
            print("[Usgromana] PromptExecutor patch skipped: no execute method")
            return

        cls._usgromana_executor_patched = True
        print(
            "[Usgromana] PromptExecutor patched: node object cache is reset on user switch"
        )

    def _install_dynamic_output_dirs(self) -> None:
        """Resolve core save-node output_dir at call time, not at first __init__."""
        try:
            import nodes
        except ImportError:
            print("[Usgromana] dynamic output_dir skipped: nodes module not found")
            return

        patched = []
        found = False
        for name in ("SaveImage", "SaveLatent"):
            cls = getattr(nodes, name, None)
            if cls is None:
                continue
            found = True
            if getattr(cls, "_usgromana_dynamic_output_dir", False):
                continue
            self._install_output_dir_property(cls)
            cls._usgromana_dynamic_output_dir = True
            patched.append(name)
        if not found:
            print("[Usgromana] dynamic output_dir skipped: SaveImage/SaveLatent not found")
            return
        if patched:
            print(
                "[Usgromana] output_dir made dynamic on core nodes: "
                + ", ".join(patched)
                + " (+subclasses)"
            )

    def _install_output_dir_property(self, cls) -> None:
        private = "_usgromana_output_dir_raw"
        ac = self

        class _RebasedOutputDir:
            def __get__(self, obj, objtype=None):
                if obj is None:
                    return self
                raw = getattr(obj, private, None)
                if not raw:
                    return ac.get_user_output_directory()
                return ac.rebase_cached_directory(raw)

            def __set__(self, obj, value):
                setattr(obj, private, value)

        setattr(cls, "output_dir", _RebasedOutputDir())

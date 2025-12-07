# --- START OF FILE routes/user.py ---
from aiohttp import web
from ..globals import routes, jwt_auth, users_db
from ..utils import user_env
import folder_paths
import os
import shutil

# Root of ComfyUI
COMFY_ROOT = folder_paths.base_path


def get_global_workflows_root() -> str:
    """
    Global/default workflows folder.

    We prefer:
      <COMFY_ROOT>/user/default/workflows
    and fall back to:
      <COMFY_ROOT>/user_data/workflows
    """
    candidates = [
        os.path.join(COMFY_ROOT, "user", "default", "workflows"),
        os.path.join(COMFY_ROOT, "user_data", "workflows"),
    ]
    for p in candidates:
        if os.path.isdir(p):
            return p
    os.makedirs(candidates[0], exist_ok=True)
    return candidates[0]


def _get_caller_admin_info(request):
    """
    Returns (is_admin: bool, username: str|None, groups: list[str])

    Used to guard admin-only actions.
    """
    token = jwt_auth.get_token_from_request(request)
    if not token:
        return False, None, ["guest"]

    try:
        payload = jwt_auth.decode_access_token(token)
        username = payload.get("username")
        _, rec = users_db.get_user(username)
        groups = [g.lower() for g in rec.get("groups", [])] if rec else ["guest"]
        is_admin = bool(rec and (rec.get("admin") or ("admin" in groups)))
        return is_admin, username, groups
    except Exception as e:
        print(f"[usgromana] admin check error: {e}")
        return False, None, ["guest"]


@routes.get("/usgromana/api/me")
async def api_me(request: web.Request) -> web.Response:
    """
    Basic identity info for the frontend.
    """
    is_admin, username, groups = _get_caller_admin_info(request)
    if username is None:
        # no / invalid token → guest
        return web.json_response(
            {
                "username": None,
                "role": "guest",
                "groups": ["guest"],
                "is_admin": False,
            }
        )

    # Choose primary role based on groups priority
    role = "guest"
    for candidate in ["admin", "power", "user", "guest"]:
        if candidate in groups:
            role = candidate
            break

    return web.json_response(
        {
            "username": username,
            "role": role,
            "groups": groups,
            "is_admin": is_admin,
        }
    )


@routes.post("/usgromana/api/user-env")
async def api_user_env(request: web.Request) -> web.Response:
    """
    Admin-only per-user environment + workflow management.

    Supported actions (JSON body):
      {
        "action": "...",
        "user": "<target username>",
        ... extra fields ...
      }

    Actions:
      - "status"           → inspect per-user env + gallery root flag
      - "list"             → list env files
      - "delete_file"      → delete a single env file
      - "purge"            → purge env root
      - "set_gallery_root" → toggle gallery root user
      - "list_workflows"   → list per-user workflows
      - "promote_workflow" → copy a user's workflow into global defaults
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    action = (data.get("action") or "").strip()
    target_user = (data.get("user") or "").strip()

    if not target_user:
        return web.json_response({"error": "Missing 'user'"}, status=400)

    # Guard: this whole endpoint is for admins
    is_admin, caller, groups = _get_caller_admin_info(request)
    if not is_admin:
        return web.json_response(
            {"error": "Admin privileges required"}, status=403
        )

    # --- STATUS ----------------------------------------------------
    if action == "status":
        files = user_env.list_user_files(target_user, max_files=200)
        gallery_root_user = user_env.get_gallery_root_user()
        is_root = gallery_root_user == target_user

        msg = f"User '{target_user}' has {len(files)} file(s) under their environment root."
        if is_root:
            msg += " This user is currently configured as the Gallery root."

        return web.json_response(
            {
                "user": target_user,
                "files": files,
                "is_gallery_root": is_root,
                "message": msg,
            }
        )

    # --- LIST FILES -----------------------------------------------
    if action == "list":
        files = user_env.list_user_files(target_user, max_files=2000)
        return web.json_response({"user": target_user, "files": files})

    # --- DELETE SINGLE FILE ---------------------------------------
    if action == "delete_file":
        rel = (data.get("file") or "").strip().replace("\\", "/")
        if not rel:
            return web.json_response({"error": "Missing 'file'"}, status=400)
        if ".." in rel or rel.startswith("/"):
            return web.json_response({"error": "Invalid file path"}, status=400)

        root = user_env.get_user_root(target_user)
        full = os.path.join(root, rel)

        if os.path.exists(full) and os.path.isfile(full):
            try:
                os.remove(full)
                msg = f"Deleted file '{rel}' for user '{target_user}'."
                print(f"[usgromana] {msg}")
                return web.json_response(
                    {"user": target_user, "file": rel, "message": msg}
                )
            except Exception as e:
                print(f"[usgromana] delete_file error: {e}")
                return web.json_response(
                    {"error": f"Failed to delete: {e}"}, status=500
                )

        msg = f"File '{rel}' not found for user '{target_user}'."
        return web.json_response(
            {"user": target_user, "file": rel, "message": msg}, status=404
        )

    # --- PURGE USER ENV ROOT --------------------------------------
    if action == "purge":
        user_env.purge_user_root(target_user)
        msg = f"Purged environment folders for user '{target_user}'."
        print(f"[usgromana] {msg}")
        return web.json_response({"user": target_user, "message": msg})

    # --- SET / CLEAR GALLERY ROOT ---------------------------------
    if action == "set_gallery_root":
        enable = bool(data.get("enable"))
        if enable:
            user_env.set_gallery_root_user(target_user)
            msg = f"Gallery root set to user '{target_user}'."
            is_root = True
        else:
            user_env.set_gallery_root_user(None)
            msg = "Gallery root cleared."
            is_root = False

        print(f"[usgromana] {msg}")
        return web.json_response(
            {"user": target_user, "message": msg, "is_gallery_root": is_root}
        )

    # --- LIST USER WORKFLOWS --------------------------------------
    if action == "list_workflows":
        workflows = user_env.list_user_workflows(target_user)
        return web.json_response(
            {
                "user": target_user,
                "workflows": workflows,
                "count": len(workflows),
            }
        )

    # --- PROMOTE WORKFLOW TO GLOBAL DEFAULTS ----------------------
    if action == "promote_workflow":
        wf_name = (data.get("workflow") or "").strip().replace("\\", "/")
        if not wf_name:
            return web.json_response({"error": "Missing 'workflow'"}, status=400)
        if ".." in wf_name or wf_name.startswith("/"):
            return web.json_response(
                {"error": "Invalid workflow name"}, status=400
            )

        delete_source = bool(data.get("delete_source"))

        user_wf_dir = user_env.get_user_workflow_dir(target_user)
        src = os.path.join(user_wf_dir, wf_name)
        if not (os.path.exists(src) and os.path.isfile(src)):
            return web.json_response(
                {
                    "error": f"Workflow '{wf_name}' not found in user folder.",
                    "user": target_user,
                },
                status=404,
            )

        global_root = get_global_workflows_root()
        dst = os.path.join(global_root, wf_name)

        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

            if delete_source:
                try:
                    os.remove(src)
                    msg = (
                        f"Workflow '{wf_name}' from user '{target_user}' "
                        f"promoted to global defaults and removed from the user's folder."
                    )
                except Exception as del_err:
                    msg = (
                        f"Workflow '{wf_name}' promoted to global defaults, "
                        f"but failed to delete source: {del_err}"
                    )
                    print(f"[usgromana] promote_workflow delete_source error: {del_err}")
            else:
                msg = (
                    f"Workflow '{wf_name}' from user '{target_user}' "
                    f"promoted to global defaults ({dst})."
                )

            print(f"[usgromana] {msg}")
            return web.json_response(
                {
                    "user": target_user,
                    "workflow": wf_name,
                    "message": msg,
                    "global_path": dst,
                    "deleted_source": bool(delete_source),
                }
            )
        except Exception as e:
            print(f"[usgromana] promote_workflow error: {e}")
            return web.json_response(
                {"error": f"Failed to promote workflow: {e}"}, status=500
            )

    # --- UNKNOWN ACTION --------------------------------------------
    return web.json_response({"error": f"Unknown action '{action}'"}, status=400)
# --- END OF FILE routes/user.py ---

from ..constants import USERS_FILE
from .json_utils import load_json_file, save_json_file

def patch_user_group(username, group_list, is_admin_bool, sfw_check=None):
    raw = load_json_file(USERS_FILE, {})
    users_data = raw.get("users", raw) if isinstance(raw, dict) else raw

    target_rec = None
    target_key = None

    iterator = users_data.items() if isinstance(users_data, dict) else enumerate(users_data)
    for k, u in iterator:
        if u.get("username") == username or u.get("user") == username:
            target_rec = u
            target_key = k
            break

    if not target_rec:
        return False

    # Groups + admin flag like before
    target_rec["groups"] = [g.lower() for g in group_list]
    target_rec["admin"] = bool(is_admin_bool)

    # NEW: optional per-user SFW flag
    if sfw_check is not None:
        target_rec["sfw_check"] = bool(sfw_check)

    # Write back into the same structure
    if isinstance(users_data, list):
        users_data[target_key] = target_rec
    else:
        users_data[target_key] = target_rec

    if isinstance(raw, dict) and "users" in raw:
        raw["users"] = users_data
    else:
        raw = users_data

    save_json_file(USERS_FILE, raw)
    return True


def delete_user_record(username):
    raw = load_json_file(USERS_FILE, {})
    users_data = raw.get("users", raw) if isinstance(raw, dict) else raw

    target_index = None
    admins_remaining = 0

    # Count admins and find target
    iterable = enumerate(users_data) if isinstance(users_data, list) else users_data.items()
    for idx, u in iterable:
        uname = u.get("username") or u.get("user")
        if u.get("admin", False) or "admin" in u.get("groups", []):
            admins_remaining += 1
        if uname == username:
            target_index = idx
            is_target_admin = u.get("admin", False) or "admin" in u.get("groups", [])

    if target_index is None:
        return False

    # Prevent deleting last admin
    if is_target_admin and admins_remaining <= 1:
        return "last_admin"

    # Remove the user
    if isinstance(users_data, list):
        users_data.pop(target_index)
    else:
        users_data.pop(target_index)

    if isinstance(raw, dict) and "users" in raw:
        raw["users"] = users_data
    else:
        raw = users_data

    save_json_file(USERS_FILE, raw)
    return True

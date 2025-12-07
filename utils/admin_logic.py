# --- START OF FILE utils/admin_logic.py ---
from ..constants import USERS_FILE
from .json_utils import load_json_file, save_json_file

def patch_user_group(username, group_list, is_admin_bool):
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
                
    if target_rec:
        target_rec["groups"] = [g.lower() for g in group_list]
        target_rec["admin"] = is_admin_bool
        
        if isinstance(users_data, list): users_data[target_key] = target_rec
        else: users_data[target_key] = target_rec
        
        if isinstance(raw, dict) and "users" in raw: raw["users"] = users_data
        else: raw = users_data
            
        save_json_file(USERS_FILE, raw)
        return True
    return False

def delete_user_record(username: str):
    """
    Returns: True (deleted), False (not found), "last_admin" (error)
    """
    raw = load_json_file(USERS_FILE, {})
    users_data = raw.get("users", raw) if isinstance(raw, dict) else raw

    # Normalize iterable
    if isinstance(users_data, dict):
        target_key = None
        target_rec = None
        for k, u in users_data.items():
            if u.get("username") == username or u.get("user") == username:
                target_key = k
                target_rec = u
                break
        if target_rec is None:
            return False

        # Check if this user is an admin
        is_admin = target_rec.get("admin", False) or \
                   ("admin" in [g.lower() for g in target_rec.get("groups", [])])

        if is_admin:
            admin_count = 0
            for v in users_data.values():
                if v.get("admin", False) or \
                   ("admin" in [g.lower() for g in v.get("groups", [])]):
                    admin_count += 1
            if admin_count <= 1:
                return "last_admin"

        del users_data[target_key]

    elif isinstance(users_data, list):
        target_index = None
        target_rec = None
        for i, u in enumerate(users_data):
            if u.get("username") == username or u.get("user") == username:
                target_index = i
                target_rec = u
                break
        if target_rec is None:
            return False

        is_admin = target_rec.get("admin", False) or \
                   ("admin" in [g.lower() for g in target_rec.get("groups", [])])

        if is_admin:
            admin_count = 0
            for v in users_data:
                if v.get("admin", False) or \
                   ("admin" in [g.lower() for g in v.get("groups", [])]):
                    admin_count += 1
            if admin_count <= 1:
                return "last_admin"

        users_data.pop(target_index)

    else:
        return False

    # Write back
    if isinstance(raw, dict) and "users" in raw:
        raw["users"] = users_data
    else:
        raw = users_data

    save_json_file(USERS_FILE, raw)
    return True
# --- START OF FILE utils/bootstrap.py ---
import os
import uuid
from ..constants import USERS_FILE, GROUPS_CONFIG_FILE, DEFAULT_GROUP_CONFIG_PATH
from .json_utils import load_json_file, save_json_file
from .admin_logic import patch_user_group
from ..globals import logger, users_db

def load_default_groups():
    cfg = load_json_file(DEFAULT_GROUP_CONFIG_PATH, None)
    if cfg is None:
        logger.error("[Usgromana] Missing default_group_config.json; using built-in fallback!")
        return {
            "admin": { "can_run": True, "can_upload": True, "can_access_manager": True, "can_access_api": True, "can_see_restricted_settings": True },
            "power": { "can_run": True, "can_upload": True, "can_access_manager": True, "can_access_api": True, "can_see_restricted_settings": False },
            "user": { "can_run": True, "can_upload": True, "can_access_manager": False, "can_access_api": True, "can_see_restricted_settings": False },
            "guest": { "can_run": False, "can_upload": False, "can_access_manager": False, "can_access_api": True, "can_see_restricted_settings": False },
        }
    return cfg

def ensure_groups_config():
    default_cfg = load_default_groups()
    current = load_json_file(GROUPS_CONFIG_FILE, {})
    changed = False

    # Add missing groups
    for role, perms in default_cfg.items():
        if role not in current:
            current[role] = perms
            changed = True

    # Add missing permission keys
    for role, perms in default_cfg.items():
        for key, value in perms.items():
            if key not in current[role]:
                current[role][key] = value
                changed = True

    if changed:
        save_json_file(GROUPS_CONFIG_FILE, current)

def ensure_guest_user():
    try:
        guest_id, guest_rec = users_db.get_user("guest")
    except Exception as e:
        logger.error(f"[Usgromana] Error checking guest user: {e}")
        return

    if guest_id is not None:
        patch_user_group("guest", ["guest"], False)
        return

    try:
        random_password = str(uuid.uuid4())
        new_guest_id = str(uuid.uuid4())
        users_db.add_user(new_guest_id, "guest", random_password, False)
        patch_user_group("guest", ["guest"], False)
        logger.info("[Usgromana] Created default 'guest' user")
    except Exception as e:
        logger.error(f"[Usgromana] Error creating guest user: {e}")
# --- START OF FILE constants.py ---
import os
import json
import warnings
import uuid

# --- Base Directories ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(CURRENT_DIR, "web")

# NOTE: If your html files are directly in web/, remove the 'html' part below
# But based on standard structure, they should be in web/html/
HTML_DIR = os.path.join(WEB_DIR, "html") 
CSS_DIR = os.path.join(WEB_DIR, "css")
JS_DIR = os.path.join(WEB_DIR, "js")
ASSETS_DIR = os.path.join(WEB_DIR, "assets")

# --- Load config.json ---
CONFIG_FILE_PATH = os.path.join(CURRENT_DIR, "config.json")
def _load_config(path):
    if os.path.exists(path):
        try:
            with open(path, "r") as f: return json.load(f)
        except: pass
    return {}

config_data = _load_config(CONFIG_FILE_PATH)

# --- Files & Paths ---
USERS_FILE = os.path.join(CURRENT_DIR, "users", "users.json")
GROUPS_CONFIG_FILE = os.path.join(CURRENT_DIR, "users", "usgromana_groups.json")
DEFAULT_GROUP_CONFIG_PATH = os.path.join(CURRENT_DIR, "users", "defaults", "default_group_config.json")
WHITELIST_FILE = os.path.join(CURRENT_DIR, "users", "whitelist.txt")
BLACKLIST_FILE = os.path.join(CURRENT_DIR, "users", "blacklist.txt")
LOG_FILE = os.path.join(CURRENT_DIR, config_data.get("log", "usgromana.log"))

# --- Configuration Values ---
LOG_LEVELS = config_data.get("log_levels", ["INFO"])
SECRET_KEY = os.getenv(config_data.get("secret_key_env", "SECRET_KEY"))
if not SECRET_KEY:
    warnings.warn("[Usgromana] SECRET_KEY not set. Using random key (logouts on restart).")
    SECRET_KEY = "".join([str(uuid.uuid4().hex) for _ in range(128)])

TOKEN_EXPIRE_MINUTES = 60 * config_data.get("access_token_expiration_hours", 12)
MAX_TOKEN_EXPIRE_MINUTES = 60 * config_data.get("max_access_token_expiration_hours", 8760)
TOKEN_ALGORITHM = "HS256"

BLACKLIST_AFTER_ATTEMPTS = config_data.get("blacklist_after_attempts", 5)
FREE_MEMORY_ON_LOGOUT = config_data.get("free_memory_on_logout", True)
FORCE_HTTPS = config_data.get("force_https", False)
SEPERATE_USERS = config_data.get("seperate_users", True)
MANAGER_ADMIN_ONLY = config_data.get("manager_admin_only", True)
MATCH_HEADERS = {"X-Forwarded-Proto": "https"}
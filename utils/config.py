"""
Utils config: legacy/secondary config loader.
Path-related settings (USERS_FILE, WHITELIST_FILE, BLACKLIST_FILE) are defined in
constants.py from config.json; this module re-exports them for code that imports
from .utils so there is a single source of truth.
"""
import os
import warnings
import uuid
import json
from typing import Dict, Any
from pathlib import Path

EXT_PATH = os.path.join(os.path.dirname(__file__), "..")
CONFIG_FILE = os.path.join(EXT_PATH, "config.json")
COMFY_ROOT = Path(__file__).resolve().parents[2]  # adjust if needed
USER_DATA_ROOT = COMFY_ROOT / "user_data"         # for future use
USER_OUTPUT_ROOT = COMFY_ROOT / "output" / "users"
USER_TEMP_ROOT = COMFY_ROOT / "temp" / "users"

def load_config(file_path: str) -> Dict[str, Any]:
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


config = load_config(CONFIG_FILE)

SECRET_KEY = os.getenv(config.get("secret_key_env", "SECRET_KEY"))

if not SECRET_KEY:
    warnings.warn(
        "The SECRET_KEY environment variable is not set. A random key will be used for this session. "
        "This will cause all users to log out on server restart."
    )
    SECRET_KEY = "".join([str(uuid.uuid4().hex) for _ in range(128)])

MATCH_HEADERS = {"X-Forwarded-Proto": "https"}

TOKEN_ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60 * config.get("access_token_expiration_hours", 12)
MAX_TOKEN_EXPIRE_MINUTES = 60 * config.get("max_access_token_expiration_hours", 8760)

# Re-export from constants so a single source of truth (config.json via constants.py)
from ..constants import USERS_FILE, WHITELIST_FILE, BLACKLIST_FILE, SEPARATE_USERS

LOG_FILE = os.path.join(EXT_PATH, config.get("log", "Usgromana.log"))
LOG_LEVELS = config.get("log_levels", ["INFO"])

# Legacy names for code that expected WHITELIST/BLACKLIST from utils
WHITELIST = WHITELIST_FILE
BLACKLIST = BLACKLIST_FILE

BLACKLIST_AFTER_ATTEMPTS = config.get("blacklist_after_attempts")

FREE_MEMORY_ON_LOGOUT = config.get("free_memory_on_logout", False)
FORCE_HTTPS = config.get("force_https", False)

# Re-export SEPARATE_USERS from constants (config key remains "seperate_users")
MANAGER_ADMIN_ONLY = config.get("manager_admin_only", False)

WEB_DIR = os.path.join(EXT_PATH, "usgromana-web")
HTML_DIR = WEB_DIR
CSS_DIR = os.path.join(WEB_DIR, "css")
JS_DIR = os.path.join(WEB_DIR, "js")
ASSETS_DIR = os.path.join(WEB_DIR, "assets")

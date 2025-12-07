# --- START OF FILE globals.py ---
from server import PromptServer
from .constants import *

# Import Utils
from .utils.access_control import AccessControl
from .utils.users_db import UsersDB
from .utils.jwt_auth import JWTAuth
from .utils.ip_filter import IPFilter
from .utils.timeout import Timeout
from .utils.logger import Logger
from .utils.sanitizer import Sanitizer

instance = PromptServer.instance
app = instance.app
routes = instance.routes

# 1. Logger & DB
logger = Logger(LOG_FILE, LOG_LEVELS)
users_db = UsersDB(USERS_FILE)

# 2. Access Control (Depends on DB + Server + Config Path)
access_control = AccessControl(
    users_db=users_db,
    server=instance,
    groups_config_file=GROUPS_CONFIG_FILE
)

# 3. Auth (Depends on DB + Access Control)
jwt_auth = JWTAuth(
    users_db=users_db,
    access_control=access_control,
    logger=logger,
    secret_key=SECRET_KEY,
    expire_minutes=TOKEN_EXPIRE_MINUTES,
    algorithm=TOKEN_ALGORITHM
)

# 4. Network Security
ip_filter = IPFilter(WHITELIST_FILE, BLACKLIST_FILE)
timeout = Timeout(ip_filter, BLACKLIST_AFTER_ATTEMPTS)
sanitizer = Sanitizer()
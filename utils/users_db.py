import bcrypt
import json
import os
import hashlib
from pathlib import Path


class UsersDB:
    def __init__(self, database: str | Path):
        self.database = database

        # Stored as: { user_id: { username, password, admin?, groups? } }
        self.users: dict = {}
        self.admin_user: tuple[str | None, dict] = (None, {})

        self._database_hash: str | None = None

        self.load_users()

    # ----------------------------
    # Password + file helpers
    # ----------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def calculate_file_hash(self) -> str:
        """Calculate the SHA256 hash of the database file."""
        if os.path.exists(self.database):
            with open(self.database, "rb") as f:
                file_data = f.read()
                return hashlib.sha256(file_data).hexdigest()
        return ""

    # ----------------------------
    # Load / save
    # ----------------------------

    def load_users(self) -> dict:
        """Load users from the database if it has changed."""
        current_hash = self.calculate_file_hash()
        if current_hash != self._database_hash:
            if os.path.exists(self.database):
                with open(self.database, "r", encoding="utf-8") as f:
                    try:
                        self.users = json.load(f)
                    except json.JSONDecodeError:
                        self.users = {}
                # 🔧 Migration / safety: ensure groups exist for all users
                self._ensure_groups_schema()
                self._database_hash = self.calculate_file_hash()
            else:
                self.users = {}
        return self.users

    def save_users(self, users: dict) -> None:
        """Save users to the database and update the hash."""
        with open(self.database, "w", encoding="utf-8") as f:
            json.dump(users, f)
        self._database_hash = self.calculate_file_hash()

    # ----------------------------
    # Schema helpers
    # ----------------------------

    def _ensure_groups_schema(self) -> None:
        """
        Ensure every user has a 'groups' list.
        - If user has admin flag but no groups → groups = ["admin"]
        - Else if no groups → groups = ["user"]
        """
        changed = False
        for uid, user in list(self.users.items()):
            # Normalize
            if "groups" not in user or not isinstance(user["groups"], list) or not user["groups"]:
                if user.get("admin"):
                    user["groups"] = ["admin"]
                else:
                    user["groups"] = ["user"]
                changed = True

        if changed:
            self.save_users(self.users)

    def _has_admin(self) -> bool:
        """Return True if any user has admin rights (admin flag OR admin group)."""
        self.load_users()
        for _uid, user in self.users.items():
            if user.get("admin"):
                return True
            groups = [g.lower() for g in user.get("groups", [])]
            if "admin" in groups:
                return True
        return False

    # ----------------------------
    # Public API
    # ----------------------------

    def add_user(self, id: str, username: str, password: str, admin: bool) -> None:
        """
        Add a user to the database.

        Rules:
        - If this is the very first user and no admin exists → force admin + groups=["admin"]
        - Otherwise:
          - if admin=True → groups=["admin"]
          - else → groups=["user"]
        """
        self.load_users()

        # Determine if we already have an admin
        has_admin = self._has_admin()

        # First user and no admin yet? Force admin.
        if not has_admin and len(self.users) == 0:
            admin = True

        # Assign groups based on admin flag
        if admin:
            groups = ["admin"]
        else:
            groups = ["user"]

        user = {
            "username": username,
            "password": self.hash_password(password),
            "admin": bool(admin),
            "groups": groups,
        }

        self.users[id] = user
        self.save_users(self.users)

    def get_user(self, username: str = "", user_id: str = "") -> tuple[str | None, dict]:
        """Retrieve a user by username or user_id. Always returns (id, user_dict_or_empty)."""
        self.load_users()

        if user_id:
            user = self.users.get(user_id)
            if user is not None:
                return user_id, user
            return None, {}

        for uid, user_data in self.users.items():
            if user_data.get("username") == username:
                return uid, user_data

        return None, {}

    def check_username_password(self, username: str, password: str) -> bool:
        """Check if the username and password match."""
        user_id, user_data = self.get_user(username)
        if not user_id or not user_data:
            return False

        return bcrypt.checkpw(
            password.encode("utf-8"), user_data["password"].encode("utf-8")
        )

    def get_admin_user(self) -> tuple[str | None, dict] | None:
        """
        Get the admin user from the database.
        Returns (id, user_dict) or (None, {}) if none.
        """
        self.load_users()
        self.admin_user = (None, {})

        for uid, user_data in self.users.items():
            groups = [g.lower() for g in user_data.get("groups", [])]
            if user_data.get("admin") or "admin" in groups:
                self.admin_user = (uid, user_data)
                break

        return self.admin_user

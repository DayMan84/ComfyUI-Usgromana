# ComfyUI Usgromana

<p align="center">
  <img src="./web/assets/Dark_Usgromana.png" width="220" />
</p>

<p align="center">
  <strong>The next-generation security, governance, permissions, and multi‑user control system for ComfyUI.</strong>
</p>

<p align="center">
  <strong>Version 2.0.3</strong> — Compatible with ComfyUI 0.33 asset scanner rename; fixes auth lockout on failed plugin import ([#24](https://github.com/DayMan84/ComfyUI-Usgromana/issues/24)) Thank you @passiony for the fix.
</p>

---

## Table of Contents
1. [Overview](#overview)  
2. [Key Features](#key-features)  
3. [Architecture](#architecture)  
4. [Installation](#installation)  
5. [Folder Structure](#folder-structure)  
6. [Configuration (config.json)](#configuration-configjson)  
7. [RBAC Roles](#rbac-roles)  
8. [UI Enforcement Layer](#ui-enforcement-layer)  
9. [Workflow Protection](#workflow-protection)  
10. [IP Rules System](#ip-rules-system)  
11. [User Environment Tools](#user-environment-tools)  
12. [Settings Panel](#settings-panel)  
13. [API Endpoints](#api-endpoints)  
14. [Backend Components](#backend-components)  
15. [Troubleshooting](#troubleshooting)  
16. [Changelog](#changelog)  
17. [License](#license)

---

## Overview

**ComfyUI Usgromana** is a comprehensive security layer that adds:

- Role‑Based Access Control (RBAC)  
- UI element gating  
- Workflow save/delete blocking  
- Transparent user folder isolation  
- IP whitelist and blacklist enforcement  
- User environment management utilities  
- A modern administrative panel with multiple tabs  
- Dynamic theme integration with the ComfyUI dark mode  
- Live UI popups, toast notifications, and visual enforcement  
- **NSFW Guard API** - Public API for NSFW detection and enforcement
- **Gallery integration** - Manual image flagging and metadata-based tagging
- **Extension Tabs API** - Allow other extensions to add custom tabs to the admin panel
- **API token generation** - Web UI and endpoints for long-lived JWT tokens (for scripts and external clients)
- **Configurable auto-blacklist** - Admin setting for failed-login IP blacklisting (default: disabled)

It replaces the older Sentinel system with a faster, cleaner, more modular architecture—fully rewritten for reliability and future expansion.

---

## Key Features

### 🔐 **RBAC Security**
Four roles: **Admin, Power, User, Guest**  
Each with configurable permissions stored in `usgromana_groups.json`.

<p align="center">
  <img src="./readme/UsgromanaLogin.png" />
</p>

### 🚫 **Save & Delete Workflow Blocking**
Non‑privileged roles cannot:
- Save workflows  
- Export workflows  
- Overwrite existing workflows  
- Delete workflow files  

<p align="center">
  <img src="./readme/AdminGroups.png" />
</p>

All blocked actions trigger:
- A server‑side 403  
- A UI toast popup explaining the denial  

### 👁️ **Dynamic UI Enforcement**
Usgromana hides or disables:
- Top‑menu items  
- Sidebar tabs  
- Settings categories  
- Extension panels  
- File menu operations  

Enforcement occurs every 1 second to catch late‑loading UI elements.

### 🌐 **IP Filtering System**
Complete backend implementation:
- Whitelist mode  
- Blacklist mode  
- **Auto-blacklist after failed login attempts** (configurable in settings; `0` = disabled)  
- Live editing in Usgromana settings tab  
- Persistent storage via `ip_filter.py` and `config.json`  

### 🗂️ **User Environment Tools**
From `user_env.py`:
- Purge a user’s folders  
- List user-owned files
- Promote user workflow to default (all user view)
- Delete single user workflow
- Toggle gallery‑folder mode

<p align="center">
  <img src="./readme/UserFiles.png" />
</p>

### 🖥️ **Transparent Themed Admin UI**
The administrative modal features:
- Transparent blurred glass background  
- Neon accent tabs  
- Integrated logo watermark  
- Scrollable permission tables  
- Responsive layout  

### 🔧 **Watcher Middleware**
A new middleware that detects:
- Forbidden workflow saves  
- Forbidden deletes  
And triggers UI-side toast popups through a custom fetch wrapper.

### 🛡️ **NSFW Guard API**
A comprehensive public API that allows other ComfyUI extensions to:
- Check user NSFW viewing permissions
- Validate image tensors, PIL Images, or file paths for NSFW content
- Integrate NSFW protection into custom nodes and extensions
- **Metadata-based tagging system** - Images are tagged with NSFW metadata stored alongside files
- **Gallery integration endpoint** - `/usgromana-gallery/mark-nsfw` for manual image flagging
- **Automatic scanning** - Background scanning of output directory with caching
- **Per-user enforcement** - SFW restrictions apply per-user based on role permissions

See [API_USAGE.md](./API_USAGE.md) for complete documentation and examples.

**Quick Example:**
```python
from api import check_tensor_nsfw, is_sfw_enforced_for_user

# In your custom node
if is_sfw_enforced_for_user():
    if check_tensor_nsfw(image_tensor):
        # Block or replace NSFW content
        image_tensor = torch.zeros_like(image_tensor)
```

**Gallery Integration:**
```javascript
// Mark an image as NSFW from gallery UI
fetch('/usgromana-gallery/mark-nsfw', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        filename: 'image.png',
        is_nsfw: true,
        score: 1.0,
        label: 'manual'
    })
});
```

---

## Architecture

```
ComfyUI
│
├── Usgromana Core
│   ├── access_control.py    → RBAC, path blocking, folder isolation
│   ├── __init__.py          → Route registration, middleware setup
│   ├── api.py               → NSFW Guard API (public interface)
│   ├── globals.py           → Shared server instances, route table
│   ├── constants.py         → Configuration paths
│   ├── routes/
│   │   ├── auth.py          → Login/Register/Token endpoints
│   │   ├── admin.py         → User & Group management, NSFW admin tools
│   │   ├── user.py          → User environment, mark-nsfw endpoint
│   │   ├── static.py        → Asset serving
│   │   └── workflow_routes.py → Workflow protection, NSFW enforcement
│   ├── utils/
│   │   ├── ip_filter.py     → Whitelist/blacklist system
│   │   ├── runtime_config.py → Mutable config.json settings (runtime)
│   │   ├── user_env.py      → User folder management
│   │   ├── sanitizer.py     → Input scrubbing
│   │   ├── logger.py        → Logging hooks
│   │   ├── timeout.py       → Rate limiting
│   │   ├── sfw_intercept/
│   │   │   ├── nsfw_guard.py → NSFW detection, metadata tagging
│   │   │   └── node_interceptor.py → Node-level image interception
│   │   └── reactor_sfw_intercept.py → ReActor SFW patch
│   └── web/
│       ├── js/usgromana_settings.js → UI enforcement + settings panel
│       ├── css/usgromana.css        → Themed UI
│       └── assets/dark_logo_transparent.png
│
└── ComfyUI (upstream)
```

---

## Installation

1. Extract Usgromana into:
```
ComfyUI/custom_nodes/Usgromana/
```

2. Restart ComfyUI.

3. On first launch, register the initial admin.

4. Open settings → **Usgromana** to configure.

### Optional: NSFW Guard and public API

For full NSFW detection and the public API (`api.py`), install optional dependencies:

```bash
pip install -r requirements-optional.txt
```

Or with pip: `pip install transformers torch pillow numpy piexif`

Without these, the extension runs normally; NSFW guard and API calls degrade gracefully (e.g. no image scanning).

---

## Folder Structure

```
Usgromana/
│
├── __init__.py              → Main entry point, route registration
├── api.py                   → NSFW Guard API (public interface)
├── globals.py               → Shared server instances, route table
├── constants.py             → Configuration paths
├── access_control.py        → RBAC, path blocking, folder isolation
│
├── routes/
│   ├── auth.py              → Login/Register/Token endpoints
│   ├── admin.py             → User & Group management, NSFW admin tools
│   ├── user.py              → User environment, mark-nsfw endpoint
│   ├── static.py           → Asset serving
│   └── workflow_routes.py   → Workflow protection, NSFW enforcement
│
├── utils/
│   ├── ip_filter.py         → Whitelist/blacklist system
│   ├── runtime_config.py    → Mutable config.json settings (runtime)
│   ├── user_env.py          → User folder management
│   ├── sanitizer.py         → Input scrubbing
│   ├── logger.py            → Logging hooks
│   ├── timeout.py           → Rate limiting
│   ├── sfw_intercept/
│   │   ├── nsfw_guard.py    → NSFW detection, metadata tagging
│   │   └── node_interceptor.py → Node-level image interception
│   └── reactor_sfw_intercept.py → ReActor SFW patch
│
├── web/
│   ├── js/usgromana_settings.js → UI enforcement + settings panel
│   ├── css/usgromana.css        → Themed UI
│   └── assets/dark_logo_transparent.png
│
└── users/
    ├── users.json
    └── usgromana_groups.json
```

---

## Configuration (config.json)

Configuration is read from `config.json` in the extension root. All paths are relative to the extension directory.

| Key | Description | Default |
|-----|-------------|--------|
| `secret_key_env` | Environment variable name for JWT secret | `SECRET_KEY` |
| `users_db` | Path to user database JSON | `users/users.json` |
| `whitelist` | Path to IP whitelist file | `users/whitelist.txt` |
| `blacklist` | Path to IP blacklist file | `users/blacklist.txt` |
| `access_token_expiration_hours` | JWT expiry in hours | `12` |
| `max_access_token_expiration_hours` | Max allowed expiry | `8760` |
| `log` | Log file name (under extension root) | `usgromana.log` |
| `log_levels` | Log levels list | `["INFO"]` |
| `blacklist_after_attempts` | Failed login/register/token attempts before an IP is auto-added to the blacklist (`0` = never) | `0` |
| `free_memory_on_logout` | Free memory on logout | `true` |
| `force_https` | Redirect HTTP to HTTPS | `false` |
| `seperate_users` | Per-user folder isolation (note: config key spelling kept for compatibility) | `true` |
| `manager_admin_only` | Restrict manager to admins | `true` |

---

## RBAC Roles

| Role | Description |
|------|-------------|
| **Admin** | Full access to all ComfyUI and Usgromana features. |
| **Power** | Elevated user with additional permissions but no admin panel access. |
| **User** | Standard user who can run workflows but cannot modify system behavior. |
| **Guest** | Fully restricted by default—cannot run, upload, save, or manage. |

Permissions are stored in:

```
users/usgromana_groups.json
```

and editable through the settings panel.

---

## UI Enforcement Layer

Usgromana dynamically modifies the UI by:
- Injecting CSS rules to hide elements
- Removing menu entries (Save, Load, Manage Extensions)
- Blocking iTools, Crystools, rgthree, ImpactPack for restricted roles
- Guarding PrimeVue dialogs (Save workflow warnings)
- Intercepting hotkeys (Ctrl+S, Ctrl+O)

All logic is contained in:

```
web/js/usgromana_settings.js
```

---

## Workflow Protection

If a user lacking permission tries to save:

1. Backend blocks the operation (`can_modify_workflows`)
2. watcher.py detects the 403 with code `"WORKFLOW_SAVE_DENIED"`
3. UI shows a centered toast popup:
   > “You do not have permission to save workflows.”

Same for delete operations.

---

## IP Rules System

Located in:

```
utils/ip_filter.py
```

### Features
- Whitelist mode: Only listed IPs allowed
- Blacklist mode: Block specific IPs
- **Auto-blacklist threshold**: After *N* failed auth attempts (login, register, or API token generation), the client IP is appended to the blacklist via `ip_filter.add_to_blacklist()`. Whitelisted IPs are exempt.
- Configurable through the **IP Rules** tab in settings (saved to `config.json` and applied live without restart)
- Manual whitelist/blacklist editing in the same tab
- Changes applied instantly to middleware

---

## User Environment Tools

From:

```
utils/user_env.py
```

Features:
- Purge a user’s input/output/temp folders
- List all user-bound files
- Toggle whether their folder functions as a gallery

Exposed through the “User Env” tab in the Usgromana settings modal.

---

## Settings Panel

Access via:
**Settings → Usgromana**

Tabs:

1. **Users & Roles**  
2. **Permissions & UI**  
3. **Default UI**  
4. **IP Rules** — whitelist, blacklist, and auto-blacklist-after-failed-attempts  
5. **User Environment**  
6. **NSFW Management**

### Extension Tabs API

Other ComfyUI extensions can register custom tabs in the Usgromana admin panel to manage their own permissions and settings. See [EXTENSION_TABS_API.md](./EXTENSION_TABS_API.md) for complete documentation.

**Quick Example:**
```javascript
window.UsgromanaAdminTabs.register({
    id: "myextension",
    label: "My Extension",
    order: 50,
    render: async (container, context) => {
        const { usersList, groupsConfig, currentUser } = context;
        container.innerHTML = `<h3>My Extension Settings</h3>`;
        // Render your content here
    }
});
```

### Additional UI Features
- Integrated logout button in the settings entry  
- Transparent blurred panel  
- Neon-accented tab bar  
- Logo watermark in top-right  

---

## API Endpoints

### NSFW Guard API (Public)
The NSFW Guard API provides programmatic access to NSFW detection and enforcement. See [API_USAGE.md](./API_USAGE.md) for complete documentation.

**Key Functions:**
- `check_tensor_nsfw(images_tensor, threshold=0.5)` - Check image tensors
- `check_image_path_nsfw(image_path, username=None)` - Check image files
- `check_pil_image_nsfw(pil_image, threshold=0.5)` - Check PIL Images
- `is_sfw_enforced_for_user(username=None)` - Check user restrictions
- `set_image_nsfw_tag(image_path, is_nsfw, score=1.0, label="manual")` - Tag images
- `get_image_nsfw_tag(image_path)` - Get existing tags

### Gallery Integration Endpoint

**POST `/usgromana-gallery/mark-nsfw`**
Manually mark an image as NSFW or SFW. Designed for integration with gallery extensions.

**Request Body:**
```json
{
    "filename": "image.png",
    "is_nsfw": true,
    "score": 1.0,      // optional, default 1.0
    "label": "manual"  // optional, default "manual"
}
```

**Response:**
```json
{
    "status": "ok",
    "message": "Image marked as NSFW",
    "filename": "image.png",
    "is_nsfw": true
}
```

**Features:**
- Recursively searches output directory subdirectories
- Security checks prevent path traversal
- Integrates with metadata tagging system
- Returns 404 if file not found, 403 for invalid paths

### Authentication Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/login` | Login page |
| POST | `/login` | User or guest login (form data); returns `jwt_token` + HttpOnly cookie |
| GET | `/register` | Registration page |
| POST | `/register` | Create user (first user becomes admin) |
| GET | `/logout` | Clear session cookie and redirect to login |
| GET | `/generate_token` | API token generation page |
| GET | `/usgromana/generate_token` | Redirect alias for the token page |
| POST | `/generate_token` | Issue JWT with custom expiry (form: `username`, `password`, `expire_hours`) |

**POST `/generate_token` response (success):**
```json
{
  "message": "JWT Token successfully generated",
  "jwt_token": "<token>"
}
```

Use the token as `Authorization: Bearer <token>` or the `jwt_token` cookie for subsequent API calls.

### Admin Endpoints

**GET/PUT `/usgromana/api/users`** - User management  
**GET/PUT `/usgromana/api/groups`** - Group/permission management  
**GET/PUT `/usgromana/api/ip-lists`** - IP whitelist, blacklist, and `blacklist_after_attempts`  
**GET/PUT `/usgromana/api/ui-defaults`** - Default UI / assets visibility  
**POST `/usgromana/api/nsfw-management`** - NSFW admin tools (scan, fix, clear)

### User Environment Endpoints

**POST `/usgromana/api/user-env`** - User folder operations (purge, list, promote)

### Extension Integration

**Extension Tabs API** - JavaScript API for extensions to add custom tabs to the admin panel. See [EXTENSION_TABS_API.md](./EXTENSION_TABS_API.md) for complete documentation.

---

## Backend Components

### `__init__.py`
- Main entry point for ComfyUI extension
- Route registration and middleware setup
- Server instance initialization

### `api.py`
- **NSFW Guard API** - Public interface for other extensions
- Functions: `check_tensor_nsfw()`, `check_image_path_nsfw()`, `is_sfw_enforced_for_user()`
- Metadata tagging: `set_image_nsfw_tag()`, `get_image_nsfw_tag()`
- User context management for worker threads

### `access_control.py`
- Folder isolation  
- RBAC  
- Middleware for blocking paths  
- Workflow protection  
- Extension gating  

### `routes/auth.py`
- JWT authentication endpoints
- Login, registration, logout, guest login
- **API token generation** (`GET`/`POST` `/generate_token`)

### `routes/admin.py`
- User & group management
- Permission editing
- NSFW management tools (scan, fix, clear)
- IP rules management (whitelist, blacklist, auto-blacklist threshold)

### `routes/user.py`
- User environment operations
- **Gallery integration**: `/usgromana-gallery/mark-nsfw` endpoint
- File management (purge, list, promote workflows)

### `routes/workflow_routes.py`
- Workflow save/delete protection
- Global NSFW enforcement on `/view` endpoint
- Workflow listing and loading

### `routes/static.py`
- Asset serving (CSS, JS, images)
- Logo and UI resources

### `utils/sfw_intercept/nsfw_guard.py`
- NSFW detection using AI models
- Metadata-based tagging system
- Background scanning and caching
- Per-user enforcement logic

### `utils/sfw_intercept/node_interceptor.py`
- Node-level image interception
- Real-time NSFW blocking in custom nodes

### `utils/reactor_sfw_intercept.py`
- ReActor extension SFW patch
- Per-user SFW enforcement for face swap operations

### `utils/sanitizer.py`
- Sanitization applies to **form POST** body and **query parameters** only. JSON request bodies (workflow save, admin APIs) are not sanitized.

### `utils/ip_filter.py`
- Whitelist & blacklist logic
- `is_whitelisted()` — exempt whitelisted IPs from auto-blacklist on failed auth
- Persistent storage; CIDR and comment support

### `utils/runtime_config.py`
- Read/write mutable settings in `config.json` at runtime (e.g. `blacklist_after_attempts`)

### `utils/timeout.py`
- Failed-attempt tracking and temporary lockouts on auth routes
- Triggers auto-blacklist when threshold is exceeded (wired to `ip_filter.add_to_blacklist()`)

### `utils/user_env.py`
- Folder operations
- Metadata tools
- User file management

---

## Tests

Minimal unit tests are in `tests/`. Run them with:

```bash
pip install pytest   # or use requirements-dev.txt
pytest tests/ -v
```

Tests cover `sanitize_name` (path traversal), `get_file_info`, and JWT encode/decode with a test secret. Running `pytest tests/` uses `tests/` as the pytest rootdir so the extension root is not loaded; `get_file_info` is skipped when the extension cannot be imported outside ComfyUI.

---

## Troubleshooting

### Missing Logo
Ensure assets exist under:
```
Usgromana/web/assets/
```
Required for login and token pages: `dark_logo_transparent.png`, `light_logo_transparent.png`, `logo_transparent.png`, `light_icon.ico`, `dark_icon.ico`.

### Login page or API token page fails to load
- Confirm `web/html/login.html` and `web/html/generate_token.html` exist.
- Check **IP Rules**: a non-empty whitelist blocks all unlisted IPs; blacklisted IPs receive 403.
- Clear stale `jwt_token` cookies or open `/logout` first.
- Restart ComfyUI after upgrading so new auth routes are registered.

### Cannot generate API token
- Use **Get API Token** on the login page (`/generate_token`) or `POST /generate_token` with form fields `username`, `password`, `expire_hours`.
- Expiry cannot exceed `max_access_token_expiration_hours` from `config.json` (default 8760 hours).
- Repeated failures may trigger lockout or auto-blacklist if configured in **IP Rules**.

### Some users blocked after failed logins
- Open **Settings → Usgromana → IP Rules**.
- Set **Auto-blacklist after failed login attempts** to `0` to disable, or raise the threshold.
- Remove mistaken entries from the blacklist textarea and click **Save Rules**.
- Whitelisted IPs are never auto-blacklisted.

### UI Not Updating
Clear browser cache or disable caching dev tools.

### Guest cannot run workflows
Check:
```
can_run = true
```
in `usgromana_groups.json`.

### mark-nsfw endpoint returns 404
- Ensure the image file exists in the output directory or subdirectories
- Check that the filename doesn't contain path traversal characters (`..`, `/`, `\`)
- Verify the file is within the output directory (security check)

### NSFW Guard API not working
- Ensure `ComfyUI-Usgromana` is loaded before your extension
- Check that the API is available: `from api import is_available; print(is_available())`
- Verify user context is set in worker threads using `set_user_context()`

### NSFW tags not persisting
- Check that metadata files (`.nsfw_metadata.json`) are being created alongside images
- Verify write permissions in the output directory
- Ensure metadata files aren't being deleted by cleanup scripts

---

## Changelog

Release history is maintained in [CHANGELOG.md](./CHANGELOG.md) (same content as [readme/CHANGELOG.md](./readme/CHANGELOG.md)).

**Latest: v2.0.3** — Compatible with ComfyUI 0.33 asset scanner rename; fixes auth lockout on failed plugin import ([#24](https://github.com/DayMan84/ComfyUI-Usgromana/issues/24)). Thanks to @passiony for the fix.

---

## License
MIT License  
You may modify and redistribute freely.


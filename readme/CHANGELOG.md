# Changelog — ComfyUI Usgromana

All notable changes to **ComfyUI Usgromana** are documented here.  
This project follows a semantic-style versioning flow adapted for active development.

---

## **v2.0.3 — ComfyUI 0.33 Asset Scanner Compatibility (2026-08-24)**

### 🐛 Bug Fixes
- **ComfyUI 0.33 import crash** — `_patch_asset_scanner_prefixes()` in `utils/comfy_user_bridge.py` now resolves `get_scan_prefixes_for_root` (0.33+) with a fallback to `get_prefixes_for_root` (pre-0.33), and patches both names so the extension loads on either API
- **Auth lockout on failed import** — fixes the partial-load failure where JWT middleware installed but login routes never registered, causing every request to return `{"error": "Authentication required"}` ([#24](https://github.com/DayMan84/ComfyUI-Usgromana/issues/24))

### 📄 Documentation
- README, CHANGELOG, and login page updated to reflect v2.0.3 as the current release

---

## **v2.0.2 — Auth, API Tokens & IP Auto-Blacklist (2026-06-15)**

### 🔑 Authentication & API Tokens
- **Restored API token generation** — `GET`/`POST` `/generate_token` and redirect alias `/usgromana/generate_token`
- **Login page fixes** — corrected HTML markup, asset fallbacks, and link to token page
- **Middleware** — token routes added to JWT public routes and auth timeout middleware
- **Frontend** — fixed generate-page timeout/action detection in `auth.js`

### 🌐 IP Rules & Security
- **Auto-blacklist setting** — new control in **IP Rules** tab: failed attempts before IP is added to blacklist (default **0** = disabled)
- **Live config** — threshold saved to `config.json` via `/usgromana/api/ip-lists` and applied without restart
- **`utils/runtime_config.py`** — runtime read/write for mutable config values
- **`is_whitelisted()`** — whitelisted IPs exempt from auto-blacklist on failed auth

### 📄 Documentation
- README, CHANGELOG, and login page updated to reflect v2.0.2 as the current release

---

## **v2.0.1 — Version Bump (2026-05-27)**
- Bumped package version from 2.0.0 to 2.0.1 in `pyproject.toml`

---

## **v2.0.0 — ComfyUI Assets Integration & Multi-User Bridge (2026-05-16)**
### 🎨 ComfyUI Assets & Generated Tab
- **Automatic assets enablement** — `prestartup_script.py` and `utils/enable_comfy_assets.py` turn on ComfyUI’s assets system without requiring `--enable-assets` on the CLI
- **Comfy-User bridge** — `utils/comfy_user_bridge.py` maps Usgromana JWT accounts to ComfyUI’s `Comfy-User` header and `owner_id` on asset references
- **Per-user asset isolation** — Output/input/temp files sync into ComfyUI’s asset registry per logged-in user
- **Generated tab support** — `GET /usgromana/api/generated-jobs` returns disk-backed outputs as `/api/jobs`-shaped rows when the UI loads history before middleware runs
- **Frontend bridge** — `web/js/comfy_user_bridge.js` injects `Comfy-User` on `api.fetchApi` and merges disk jobs into the Generated tab
- **ComfyUI multi-user picker disabled** — Prestartup clears `--multi-user` so login stays on Usgromana sign-in only

### ⚙️ Default UI (Assets Visibility)
- **New admin tab: Default UI** — Controls global **Assets / Imports** visibility (`user_specific`, `allow_all`, `disable_all`)
- **API** — `GET/PUT /usgromana/api/ui-defaults` for admins; defaults seeded from `users/defaults/default_ui_defaults.json`
- **Independent NSFW filtering** — `utils/nsfw_media_filter.py` applies per-user SFW policy to assets and gallery regardless of visibility mode

### 🛡️ NSFW & Media Paths
- **Centralized path resolution** — `utils/media_paths.py` for `/view`, `/static_gallery`, and output lookups
- **Assets list filtering** — NSFW assets hidden on list, detail, and download when SFW is enforced for the session
- **Improved `/view` and gallery blocking** — Middleware uses shared resolvers for output and temp images

### 🔔 UI & Extension APIs
- **Grouped denial toasts** — `web/js/denial_toasts.js` stacks workflow/manager denials with deduplication and “Clear all”
- **Radial Menu API** — Extensions register quick-action buttons on the floating Usgromana button; see `readme/RADIAL_MENU_API.md`
- **Session identity** — `GET /usgromana/api/me` returns username, `user_id`, role, groups, and current assets visibility mode

### 🏗️ Data Layout & Quality
- **Safe `users/` bootstrap** — `utils/users_storage.py` creates layout without overwriting live data; resolves legacy `users.json` paths
- **Unit tests** — `tests/` with JWT round-trip and workflow helper coverage; `requirements-dev.txt` for pytest
- **Async disconnect quieting** — `utils/asyncio_client_disconnect.py` reduces log noise on client disconnect
- **Documentation** — API guides moved under `readme/` (`API_USAGE.md`, `EXTENSION_TABS_API.md`, `RADIAL_MENU_API.md`)

### 🐛 Fixes & Config
- **`auto_enable_comfy_assets`** — New `config.json` key (default `true`) to control prestartup assets enablement
- **`enable_guest_account`** — Optional guest user creation and guest login (merged from `main`; default `true`)
- **Sanitizer scope** — Documented: form POST and query params only; JSON bodies are not sanitized

---

## **v1.9.0 — Extension Tabs API & Performance Improvements (2025-12-12)**
### 🎨 Extension Tabs API
- **New API for extensions** - Extensions can now register custom tabs in the Usgromana admin panel
- **Tab registry system** - Global `window.UsgromanaAdminTabs` API for tab registration and management
- **Context data access** - Extension tabs receive usersList, groupsConfig, and currentUser in render context
- **Ordering support** - Tabs can specify order/position for custom placement
- **Error handling** - Graceful error handling prevents extension tab failures from breaking admin panel
- **Security** - XSS protection with HTML escaping and ID validation
- **Documentation** - Complete API documentation in `EXTENSION_TABS_API.md`

### 🔧 IP Filtering Improvements
- **CIDR support** - IP whitelist/blacklist now supports CIDR ranges (e.g., `192.168.1.0/24`)
- **Comment support** - Lines starting with `#` are ignored in IP list files
- **Type fixes** - Corrected return type annotations (`tuple[list, list]` instead of `tuple[dict, dict]`)
- **Cache bug fix** - Fixed bug where cached lists weren't returned correctly when hash unchanged
- **Improved file writing** - Better handling of newlines when appending to blacklist
- **PUT endpoint implementation** - Completed the `/usgromana/api/ip-lists` PUT endpoint for saving IP rules

### ⚡ Performance Optimizations
- **DOM query caching** - Cached DOM queries in enforcement interval to reduce repeated lookups
- **Interval cleanup** - Stored interval IDs for potential cleanup and added logic to stop intervals when work is complete
- **MutationObserver management** - Proper disconnect logic and prevention of multiple observers
- **Debounced updates** - Added debouncing to menu text updates to prevent excessive calls
- **Efficient menu queries** - Optimized menu item queries with caching and reduced scanning
- **Logout button optimization** - Interval stops automatically once logout button is created

### 🐛 Bug Fixes
- **Settings menu capitalization** - Fixed lowercase "u" in settings menu by updating registration ID
- **Guest logout visibility** - Ensured logout button and usgromana menu are always visible for guest accounts
- **JavaScript string escaping** - Fixed `\\n` to `\n` and regex patterns in IP rules UI
- **Variable name fix** - Fixed undefined variable references in tab rendering

---

## **v1.8.0 — NSFW Guard API & Gallery Integration (2025-12-12)**
### 🛡️ NSFW Guard API Enhancements
- **Metadata-based tagging system** - Images are now tagged with NSFW metadata stored alongside files (`.nsfw_metadata.json`)
- **Gallery integration endpoint** - New `/usgromana-gallery/mark-nsfw` endpoint for manual image flagging from gallery UIs
- **Recursive file search** - mark-nsfw endpoint now searches subdirectories to find images
- **Enhanced API functions** - Added `set_image_nsfw_tag()` for programmatic tagging
- **Background scanning** - Automatic scanning of output directory with intelligent caching
- **Per-user enforcement** - SFW restrictions apply per-user based on role permissions

### 🔗 Gallery Integration
- **ComfyUI-Usgromana-Gallery compatibility** - Full integration with gallery extension
- **Manual flagging** - Users can manually mark images as NSFW/SFW through gallery UI
- **Metadata persistence** - NSFW tags persist across server restarts via metadata files

### 🛠️ Route Registration Improvements
- **Explicit route registration** - Routes are now explicitly registered to ensure availability
- **Middleware whitelisting** - Gallery routes are properly whitelisted in workflow middleware
- **Route verification** - Startup verification ensures all routes are properly registered

### 📂 Architecture Updates
- **Modular route structure** - Routes organized into dedicated modules (`routes/` directory)
- **Separation of concerns** - NSFW logic separated into `utils/sfw_intercept/` module
- **Public API module** - `api.py` provides clean public interface for other extensions

---

## **v1.7.5 — Critical Issue Resolution (2025-12-11)**
### 🛠️ Admin Workflow Fixes
- Resolved issue which barred admins from deleting default workflows
- Resolved issue with extension name causing UI block to fail

---

## **v1.7.0 — Updated Extension Logic & Added SFW Toggle (2025-12-10)**
### 🛠️ Admin User Group Extension List
- Resolved issue which caused duplicate extensions to be listed
- List now accounts for explicitly listed extensions
### 🛠️ Per User SFW Reactor Intercept (Highly Experimental)
- Admin can now toggle SFW on/off per user
- `utils/reactor_sfw_intercept.py` (added new file)

---

## **v1.6.0 — Refactor & Update User Workflow Administration (2025-12-8)**
### 📂 User Files Additions
- **Monolith Addition:** Added options to select and delete individual files & Promote Workflows
  - `routes/user.py` (Updated information passage)
  - `web/usgromana_settings.js` (updated the middleware and UI architecture)

---

## **v1.5.0 — Modular Refactor & Architecture Overhaul (2025-12-6)**
### 🏗️ Architectural Refactor
- **Monolith Split:** Deconstructed the massive `usgromana.py` into modular route handlers:
  - `routes/auth.py` (Login/Register/Token)
  - `routes/admin.py` (User & Group management)
  - `routes/user.py` (User environment & status)
  - `routes/static.py` (Asset serving)
- **Circular Dependency Resolution:** Introduced `globals.py` to handle shared server instances and `constants.py` to centralize configuration paths.
- **Logic Decoupling:** Moved business logic out of HTTP handlers into dedicated utilities (`utils/admin_logic.py`, `utils/json_utils.py`, `utils/bootstrap.py`).

### 🛠️ Stability & Fixes
- **Startup Resilience:** Added auto-creation logic for missing static folders (`web/css`, `web/js`, `web/html`) to prevent `aiohttp` crash on first run.
- **Windows Pathing:** Fixed `FileNotFoundError` and path resolution issues on Windows environments.
- **Middleware Fixes:** Restored missing `create_folder_access_control_middleware` and fixed import errors in `watcher.py`.
- **Config Correction:** Resolved missing `MAX_TOKEN_EXPIRE_MINUTES` constant that prevented server startup.

### 📂 Frontend Reorganization
- Restructured `web/` directory for cleaner separation of concerns.
- Consolidated ComfyUI extension scripts (`usgromana_settings.js`, `logout.js`, `injectCSS.js`) to ensure reliable auto-loading.
- Moved HTML templates to `web/html/` and updated static route mappings.
- Removed legacy `admin.js` to prevent conflicts with the integrated Settings UI.

---

## **v1.4.0 — Major Security & UI Expansion**
### 🔥 New Features
- Added **multi-tab Usgromana Settings Panel**  
  - Users & Roles  
  - Permissions & UI  
  - IP Rules  
  - User Environment  
- Introduced **logout button** inside Usgromana settings.
- Implemented **transparent glass UI theme** with background blur.
- Added **Usgromana logo watermark** support in upper-right corner.

### 🔐 Security Enhancements
- Full **save/delete workflow blocking** for restricted roles.
- New `watcher.py` middleware to detect backend 403s and send structured UI warnings.
- Unified blocking under `WORKFLOW_SAVE_DENIED` and `WORKFLOW_DELETE_DENIED` codes.
- Strengthened **RBAC defaults** for guest accounts.
- Added **extension UI gating** via CSS + runtime menu removal.

### 🧠 Backend Improvements
- New IP filtering system (`ip_filter.py`) with whitelist + blacklist modes.
- New User Environment tools (`user_env.py`) including:  
  - Folder purge  
  - File listing  
  - Gallery-mode toggles  
- Added `create_usgromana_middleware()` unified security layer.
- Path blocking now includes extension routes, workflow endpoints, manager access, and asset paths.

---

## **v1.3.0 — UI Enforcement Engine Overhaul**
### ✨ Enhancements
- Added dynamic scanning of:  
  - PrimeVue menus  
  - Sidebar buttons  
  - Settings categories  
- Enforcement now applies every second to catch late UI loads.
- Added hotkey interception (Ctrl+S / Ctrl+O) for restricted roles.
- Rebuilt `patchSaveConfirmDialog` to override PrimeVue dialogs.

### 🛠 Stability Updates
- Resolved issues where guests could open extension settings.
- Added safe defaults for undefined permissions per role.

---

## **v1.2.0 — Folder Isolation & User Paths**
### 🔧 New Features
- Added per-user:  
  - input directory  
  - output directory  
  - temp directory  
- Automatic directory creation with fallback to “public” user.
- Added `filename_prefix` rewriting for isolated naming.

### 🐞 Fixes
- Corrected queue ownership tracking.
- Fixed history objects containing mixed-user entries.

---

## **v1.1.0 — JWT Authentication Integration**
### 🚀 Additions
- Added JWT login, registration, expiration, and cookie storage.
- Implemented guest login with auto-created “guest” user.
- Created protections to ensure guest cannot escalate privileges.

### ⚙ Backend
- Refactored user database operations.
- Added detection for first-time admin setup.

---

## **v1.0.0 — Initial Release**
- Base RBAC system  
- Permission flags stored in `usgromana_groups.json`  
- Middleware for execution, upload, manager access  
- Basic UI blocking  
- Initial Usgromana settings entry (pre-tabs)

---

## Upcoming Features (Planned for v1.5+)
- Live audit logging panel  
- Real-time session viewer  
- Admin ability to force logout users  
- Per-user storage quotas  
- Automated workflow sandboxing  
- Theme customization panel

---
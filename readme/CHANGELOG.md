# Changelog — ComfyUI Usgromana

All notable changes to **ComfyUI Usgromana** are documented here.  
This project follows a semantic-style versioning flow adapted for active development.

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
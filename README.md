# ComfyUI Usgromana

<p align="center">
  <img src="./web/assets/dark_logo_transparent.png" width="220" />
</p>

<p align="center">
  <strong>The next-generation security, governance, permissions, and multi‑user control system for ComfyUI.</strong>
</p>

---

## Table of Contents
1. [Overview](#overview)  
2. [Key Features](#key-features)  
3. [Architecture](#architecture)  
4. [Installation](#installation)  
5. [Folder Structure](#folder-structure)  
6. [RBAC Roles](#rbac-roles)  
7. [UI Enforcement Layer](#ui-enforcement-layer)  
8. [Workflow Protection](#workflow-protection)  
9. [IP Rules System](#ip-rules-system)  
10. [User Environment Tools](#user-environment-tools)  
11. [Settings Panel](#settings-panel)  
12. [Backend Components](#backend-components)  
13. [Troubleshooting](#troubleshooting)  
14. [License](#license)

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

It replaces the older Sentinel system with a faster, cleaner, more modular architecture—fully rewritten for reliability and future expansion.

---

## Key Features

### 🔐 **RBAC Security**
Four roles: **Admin, Power, User, Guest**  
Each with configurable permissions stored in `usgromana_groups.json`.

<p align="center">
  <img src="./readme/UsgromanaLogin.png" width="400" />
</p>

### 🚫 **Save & Delete Workflow Blocking**
Non‑privileged roles cannot:
- Save workflows  
- Export workflows  
- Overwrite existing workflows  
- Delete workflow files  

<p align="center">
  <img src="./readme/AdminGroups.png" width="400" />
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
- Live editing in Usgromana settings tab  
- Persistent storage via `ip_filter.py`  

### 🗂️ **User Environment Tools**
From `user_env.py`:
- Purge a user’s folders  
- List user-owned files  
- Toggle gallery‑folder mode

<p align="center">
  <img src="./readme/UserFiles.png" width="400" />
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

---

## Architecture

```
ComfyUI
│
├── Usgromana Core
│   ├── access_control.py    → RBAC, path blocking, folder isolation
│   ├── usgromana.py         → Route setup, JWT, auth flows, settings API
│   ├── watcher.py           → Intercepts 403 codes and triggers popups
│   ├── utils/
│   │   ├── ip_filter.py     → Whitelist/blacklist system
│   │   ├── user_env.py      → User folder management
│   │   ├── sanitizer.py     → Input scrubbing
│   │   ├── logger.py        → Logging hooks
│   │   └── timeout.py       → Rate limiting
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

---

## Folder Structure

```
Usgromana/
│
├── access_control.py
├── usgromana.py
│
├── utils/
│   ├── ip_filter.py
│   ├── user_env.py
│   ├── watcher.py
│   └── sanitizer.py
│
├── web/
│   ├── js/usgromana_settings.js
│   ├── css/usgromana.css
│   └── assets/dark_logo_transparent.png
│
└── users/
    ├── users.json
    └── usgromana_groups.json
```

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
- Configurable through new “IP Rules” tab in settings
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
3. **IP Rules**  
4. **User Environment**

### Additional UI Features
- Integrated logout button in the settings entry  
- Transparent blurred panel  
- Neon-accented tab bar  
- Logo watermark in top-right  

---

## Backend Components

### `access_control.py`
- Folder isolation  
- RBAC  
- Middleware for blocking paths  
- Workflow protection  
- Extension gating  

### `usgromana.py`
- All routes `/usgromana/api/*`
- JWT auth handling
- Registration & login flows
- Guest login

### `watcher.py`
- Intercepts 403s
- Sends structured JS events

### `ip_filter.py`
- Whitelist & blacklist logic
- Persistent storage

### `user_env.py`
- Folder operations
- Metadata tools

---

## Troubleshooting

### Missing Logo
Ensure the file exists:
```
Usgromana/web/assets/dark_logo_transparent.png
```

### UI Not Updating
Clear browser cache or disable caching dev tools.

### Guest cannot run workflows
Check:
```
can_run = true
```
in `usgromana_groups.json`.

---

## License
MIT License  
You may modify and redistribute freely.


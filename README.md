# ComfyUI-Usgromana

## Overview
ComfyUI-Usgromana is a security and user-governance layer for ComfyUI that introduces role-based access control (RBAC), UI enforcement, workflow save/delete blocking, IP filtering, user environment tooling, and a full-featured administrative interface.

## Key Features
- Four-tier RBAC: admin, power, user, guest
- UI and API permission enforcement
- Workflow save/delete protection with toast notifications
- IP whitelist/blacklist management
- User environment controls: purge folders, inspect files, toggle gallery mode
- Per-role extension access control
- Integrated logout within settings
- Themed settings UI panel with transparency and logo watermark

## Installation
1. Place the Usgromana folder into ComfyUI/custom_nodes.
2. Restart ComfyUI.
3. Create admin user on first launch.
4. Access Usgromana settings via ComfyUI → Settings → Usgromana.

## Folder Structure
custom_nodes/
  Usgromana/
    usgromana.py
    access_control.py
    utils/
      ip_filter.py
      user_env.py
      sanitizer.py
      watcher.py
    web/
      js/usgromana_settings.js
      css/usgromana.css
      assets/logo.png
    users/
      users.json
      usgromana_groups.json

## RBAC Overview
Admins have full privileges. Power users have elevated capabilities. Normal users run workflows but cannot save or modify them. Guests are fully restricted unless explicitly allowed.

## UI Enforcement
Usgromana injects CSS and JavaScript to block UI elements dynamically based on role. Elements include:
- Save/Load/Export buttons
- Extension UI panels
- Sidebar buttons
- Settings categories

## Workflow Protection
Non‑privileged roles attempting to save or delete workflows are blocked. A toast popup explains the restriction. Ctrl+S and Ctrl+O are intercepted.

## IP Filtering
Advanced IP rules are provided via utils/ip_filter.py:
- Whitelist mode: only approved IPs allowed
- Blacklist mode: deny listed IPs
- Usgromana settings UI includes tabs for adding/removing IPs

## User Environment Tools
From utils/user_env.py:
- Purge user folders
- List files
- Toggle gallery-mode folder

## Admin Panel Tabs
1. Users & Roles  
2. Permissions & UI  
3. IP Rules  
4. User Environment  

## Logout Integration
The Usgromana settings entry includes a logout button that clears JWT and redirects to login.

## Theming
The UI panel supports:
- Transparency blur
- Dark theme matching ComfyUI
- Logo watermark background
- High‑contrast elements for readability

## Troubleshooting
- Missing logo: ensure assets/logo.png and correct static route.
- Permissions not updating: restart browser to clear cached JS.
- Guest unable to run workflows: adjust can_run and can_access_api in groups config.

## License
MIT License


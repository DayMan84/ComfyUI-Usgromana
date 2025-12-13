# --- START OF FILE routes/admin.py ---
from aiohttp import web
from ..globals import routes, jwt_auth, users_db, ip_filter
from ..constants import GROUPS_CONFIG_FILE, DEFAULT_GROUP_CONFIG_PATH, WHITELIST_FILE, BLACKLIST_FILE, USERS_FILE
from ..utils.json_utils import load_json_file, save_json_file
from ..utils.admin_logic import patch_user_group, delete_user_record
from ..utils.bootstrap import load_default_groups

def is_admin(request):
    token = jwt_auth.get_token_from_request(request)
    if not token: return False
    try:
        p = jwt_auth.decode_access_token(token)
        _, u = users_db.get_user(p['username'])
        return u.get('admin', False) or "admin" in u.get('groups', [])
    except: return False

@routes.get("/usgromana/api/groups")
async def api_groups(request):
    default_cfg = load_default_groups()
    return web.json_response({"groups": load_json_file(GROUPS_CONFIG_FILE, default_cfg)})

@routes.put("/usgromana/api/groups")
async def api_update_groups(request):
    if not is_admin(request): return web.json_response({"error": "Admin only"}, status=403)
    try:
        data = await request.json()
        new_groups = data.get("groups", {})
        current = load_json_file(GROUPS_CONFIG_FILE, {})
        for g, perms in new_groups.items():
            g_lower = g.lower()
            if g_lower not in current: current[g_lower] = {}
            for k, v in perms.items():
                current[g_lower][k] = bool(v)
        save_json_file(GROUPS_CONFIG_FILE, current)
        return web.json_response({"status": "ok"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

@routes.get("/usgromana/api/users")
async def api_users(request):
    # Security: You might want to restrict this to admins only too
    if not is_admin(request): return web.json_response({"error": "Admin only"}, status=403)
    
    raw = load_json_file(USERS_FILE, {})
    users_list = []
    iterable = raw.get("users", raw).values() if isinstance(raw.get("users", raw), dict) else raw.get("users", raw)
    for u in iterable:
        users_list.append({
            "username": u.get("username", "unknown"),
            "groups": [g.lower() for g in u.get("groups", ["user"])],
            "is_admin": u.get("admin", False),
            # NEW: per-user SFW flag; default = True (SFW enabled)
            "sfw_check": u.get("sfw_check", True),
        })
    return web.json_response({"users": users_list})

@routes.put("/usgromana/api/users/{target_user}")
async def api_update_user_route(request):
    if not is_admin(request):
        return web.json_response({"error": "Admin only"}, status=403)

    target = request.match_info["target_user"]
    data = await request.json()

    groups = [g.lower() for g in data.get("groups", [])]
    is_admin_flag = "admin" in groups

    # NEW: optional SFW flag
    sfw_check = data.get("sfw_check", None)

    success = patch_user_group(target, groups, is_admin_flag, sfw_check)
    if success:
        return web.json_response({"status": "ok"})
    return web.Response(status=404)

@routes.delete("/usgromana/api/users/{target_user}")
async def api_delete_user_route(request):
    if not is_admin(request): return web.json_response({"error": "Admin only"}, status=403)
    target = request.match_info["target_user"]
    if target == "guest": return web.json_response({"error": "Cannot delete guest"}, status=400)
    
    result = delete_user_record(target)
    if result == "last_admin": return web.json_response({"error": "Cannot delete last admin"}, status=400)
    if result is False: return web.Response(status=404)
    return web.json_response({"status": "ok"})

@routes.get("/usgromana/api/ip-lists")
async def api_ip_lists(request):
    whitelist, blacklist = ip_filter.load_filter_list()
    return web.json_response({
        "whitelist": [str(ip) for ip in (whitelist or [])],
        "blacklist": [str(ip) for ip in (blacklist or [])]
    })

@routes.put("/usgromana/api/ip-lists")
async def api_update_ip_lists(request):
    if not is_admin(request): 
        return web.json_response({"error": "Admin only"}, status=403)
    try:
        data = await request.json()
        whitelist = data.get("whitelist", [])
        blacklist = data.get("blacklist", [])
        
        # Validate and write whitelist
        import ipaddress
        
        # Write whitelist
        with open(WHITELIST_FILE, "w") as f:
            for ip_entry in whitelist:
                ip_entry = ip_entry.strip()
                if ip_entry:
                    try:
                        # Validate IP or CIDR
                        try:
                            ipaddress.ip_address(ip_entry)
                        except ValueError:
                            ipaddress.ip_network(ip_entry, strict=False)
                        f.write(ip_entry + "\n")
                    except ValueError:
                        # Skip invalid entries
                        continue
        
        # Write blacklist
        with open(BLACKLIST_FILE, "w") as f:
            for ip_entry in blacklist:
                ip_entry = ip_entry.strip()
                if ip_entry:
                    try:
                        # Validate IP or CIDR
                        try:
                            ipaddress.ip_address(ip_entry)
                        except ValueError:
                            ipaddress.ip_network(ip_entry, strict=False)
                        f.write(ip_entry + "\n")
                    except ValueError:
                        # Skip invalid entries
                        continue
        
        # Reload the filter lists to update in-memory cache
        ip_filter.load_filter_list()
        
        return web.json_response({"status": "ok"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

@routes.post("/usgromana/api/nsfw-management")
async def api_nsfw_management(request):
    """Admin-only NSFW management endpoints."""
    if not is_admin(request):
        return web.json_response({"error": "Admin only"}, status=403)
    
    try:
        data = await request.json()
        action = data.get("action", "").strip()
        
        print(f"[Usgromana] NSFW management action: {action}")
        
        from ..utils.sfw_intercept.nsfw_guard import (
            scan_all_images_in_output_directory,
            fix_incorrectly_cached_tags,
            clear_all_nsfw_tags
        )
        
        # Run blocking operations in executor to avoid blocking the event loop
        import asyncio
        loop = asyncio.get_event_loop()
        
        if action == "scan_all":
            force_rescan = bool(data.get("force_rescan", False))
            print(f"[Usgromana] Starting scan_all (force_rescan={force_rescan}) in executor...")
            result = await loop.run_in_executor(
                None, 
                scan_all_images_in_output_directory, 
                force_rescan
            )
            print(f"[Usgromana] scan_all completed: {result}")
            return web.json_response({
                "status": "ok",
                "message": f"Scanned {result['scanned']} images. Found {result['nsfw_found']} NSFW images.",
                "stats": result
            })
        
        elif action == "fix_incorrect":
            print(f"[Usgromana] Starting fix_incorrect in executor...")
            fixed_count = await loop.run_in_executor(
                None,
                fix_incorrectly_cached_tags
            )
            print(f"[Usgromana] fix_incorrect completed: {fixed_count} fixed")
            return web.json_response({
                "status": "ok",
                "message": f"Fixed {fixed_count} incorrectly cached images.",
                "fixed_count": fixed_count
            })
        
        elif action == "clear_all_tags":
            print(f"[Usgromana] Starting clear_all_tags in executor...")
            cleared_count = await loop.run_in_executor(
                None,
                clear_all_nsfw_tags
            )
            print(f"[Usgromana] clear_all_tags completed: {cleared_count} cleared")
            return web.json_response({
                "status": "ok",
                "message": f"Cleared NSFW tags from {cleared_count} images.",
                "cleared_count": cleared_count
            })
        
        else:
            return web.json_response({"error": f"Unknown action: {action}"}, status=400)
    
    except Exception as e:
        import traceback
        print(f"[Usgromana] NSFW management error: {e}")
        traceback.print_exc()
        return web.json_response({"error": str(e)}, status=500)
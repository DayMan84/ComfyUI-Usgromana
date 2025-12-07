# --- START OF FILE routes/auth.py ---
import os
import uuid
from aiohttp import web
from ..globals import routes, users_db, jwt_auth, logger, timeout
from ..constants import HTML_DIR
from ..utils.bootstrap import ensure_guest_user, ensure_groups_config
from ..utils.ip_filter import get_ip
from ..utils import user_env

@routes.get("/register")
async def get_register(request: web.Request) -> web.Response:
    path = os.path.join(HTML_DIR, "register.html")
    if not os.path.exists(path): return web.Response(text="register.html not found", status=404)
    with open(path, "r") as f: html_content = f.read()
    if not users_db.load_users():
        html_content = html_content.replace("{{ X-Admin-User }}", "true")
    else:
        html_content = html_content.replace("{{ X-Admin-User }}", "false")
    return web.Response(body=html_content, content_type="text/html")

@routes.post("/register")
async def post_register(request: web.Request) -> web.Response:
    sanitized_data = request.get("_sanitized_data", {})
    ip = get_ip(request)
    new_username = sanitized_data.get("new_user_username")
    new_password = sanitized_data.get("new_user_password")
    username = sanitized_data.get("username")
    password = sanitized_data.get("password")

    admin_user = users_db.get_admin_user()
    is_first_admin = (admin_user[0] is None)

    if not is_first_admin:
        if not users_db.check_username_password(username, password):
            timeout.add_failed_attempt(ip)
            return web.json_response({"error": "Invalid admin credentials"}, status=403)

    if None not in users_db.get_user(new_username):
        return web.json_response({"error": "Username exists"}, status=400)

    users_db.add_user(str(uuid.uuid4()), new_username, new_password, is_first_admin)

    # Create directory immediately
    user_env.get_user_workflow_dir(new_username)

    if is_first_admin:
        ensure_groups_config()
        ensure_guest_user()

    logger.registration_success(ip, new_username, username if not is_first_admin else None)
    timeout.remove_failed_attempts(ip)
    return web.json_response({"message": "User registered"})

@routes.get("/login")
async def get_login(request: web.Request) -> web.Response:
    if not users_db.load_users(): return web.HTTPFound("/register")
    if jwt_auth.get_token_from_request(request): return web.HTTPFound("/logout")
    path = os.path.join(HTML_DIR, "login.html")
    return web.FileResponse(path) if os.path.exists(path) else web.Response(text="login.html not found", status=404)

@routes.post("/login")
async def post_login(request: web.Request) -> web.Response:
    sanitized_data = request.get("_sanitized_data", {})
    ip = get_ip(request)
    
    if str(sanitized_data.get("guest_login", "false")).lower() == "true":
        ensure_guest_user()
        guest_id, _ = users_db.get_user("guest")
        if not guest_id: return web.json_response({"error": "Guest disabled"}, status=500)
        
        user_env.get_user_workflow_dir("guest")
        
        token = jwt_auth.create_access_token({"id": guest_id, "username": "guest"})
        resp = web.json_response({"message": "Guest login", "jwt_token": token})
        resp.set_cookie("jwt_token", token, httponly=True, samesite="Strict")
        logger.login_success(ip, "guest")
        timeout.remove_failed_attempts(ip)
        return resp

    username = sanitized_data.get("username")
    password = sanitized_data.get("password")

    if users_db.check_username_password(username, password):
        user_id, _ = users_db.get_user(username)
        
        user_env.get_user_workflow_dir(username)
        
        token = jwt_auth.create_access_token({"id": user_id, "username": username})
        resp = web.json_response({"message": "Login successful", "jwt_token": token})
        resp.set_cookie("jwt_token", token, httponly=True, samesite="Strict")
        logger.login_success(ip, username)
        timeout.remove_failed_attempts(ip)
        return resp

    timeout.add_failed_attempt(ip)
    return web.json_response({"error": "Invalid credentials"}, status=401)

@routes.get("/logout")
async def get_logout(request: web.Request) -> web.Response:
    resp = web.HTTPFound("/login")
    resp.del_cookie("jwt_token", path="/")
    return resp
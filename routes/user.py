# --- START OF FILE routes/user.py ---
from aiohttp import web
from ..globals import routes, jwt_auth, users_db
from ..utils import user_env

@routes.get("/usgromana/api/me")
async def api_me(request):
    token = jwt_auth.get_token_from_request(request)
    if not token: return web.json_response({"role": "guest", "is_admin": False})
    
    try:
        payload = jwt_auth.decode_access_token(token)
        username = payload.get("username")
        _, rec = users_db.get_user(username)
        groups = [g.lower() for g in rec.get("groups", [])] if rec else ["guest"]
        return web.json_response({
            "username": username,
            "role": groups[0] if groups else "guest",
            "groups": groups,
            "is_admin": "admin" in groups or rec.get("admin") is True
        })
    except:
        return web.json_response({"role": "guest", "is_admin": False})

@routes.post("/usgromana/api/user-env")
async def api_user_env(request: web.Request) -> web.Response:
    # ... Reuse logic from original file or import from user_env ...
    data = await request.json()
    action = data.get("action")
    target_user = data.get("user")
    
    if action == "status":
        files = user_env.list_user_files(target_user, max_files=200)
        return web.json_response({"user": target_user, "files": files})
    
    # ...
    return web.json_response({"status": "ok"})
"""HTTP API for sharing gallery images with other Usgromana accounts."""

from aiohttp import web

from ..globals import jwt_auth, routes, users_db
from ..utils.image_share_access import get_share_store


def _caller(request: web.Request) -> tuple[str | None, str | None]:
    token = jwt_auth.get_token_from_request(request)
    if not token:
        return None, None
    try:
        payload = jwt_auth.decode_access_token(token)
    except Exception:
        return None, None
    username = payload.get("username")
    user_id = payload.get("id")
    if not username or not user_id:
        return None, None
    stored_id, _record = users_db.get_user(str(username))
    if stored_id != user_id:
        return None, None
    return str(user_id), str(username)


def _known_usernames() -> set[str]:
    users_db.load_users()
    return {
        user.get("username")
        for user in users_db.users.values()
        if isinstance(user, dict) and user.get("username")
    }


def _json_error(message: str, status: int = 400) -> web.Response:
    return web.json_response({"ok": False, "error": message}, status=status)


async def _body(request: web.Request) -> dict:
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


@routes.get("/usgromana/api/image-shares/accounts")
async def list_share_accounts(request: web.Request) -> web.Response:
    user_id, username = _caller(request)
    if not user_id:
        return _json_error("Authentication required", 401)
    others = sorted(name for name in _known_usernames() if name != username)
    return web.json_response({"ok": True, "users": others})


@routes.post("/usgromana/api/image-shares/visibility")
async def image_share_visibility(request: web.Request) -> web.Response:
    user_id, username = _caller(request)
    if not user_id:
        return _json_error("Authentication required", 401)
    data = await _body(request)
    relpaths = data.get("relpaths") or []
    if isinstance(relpaths, str):
        relpaths = [relpaths]
    shares = get_share_store().visibility(user_id, relpaths)
    images = [
        {
            "relpath": item["relpath"],
            "owner": username,
            "viewers": item["viewers"],
        }
        for item in shares
    ]
    return web.json_response({"ok": True, "images": images})


@routes.post("/usgromana/api/image-shares")
async def share_images(request: web.Request) -> web.Response:
    user_id, username = _caller(request)
    if not user_id:
        return _json_error("Authentication required", 401)
    data = await _body(request)
    relpaths = data.get("relpaths") or []
    usernames = data.get("usernames") or []
    if isinstance(relpaths, str):
        relpaths = [relpaths]
    if isinstance(usernames, str):
        usernames = [usernames]
    usernames = [name for name in usernames if name != username]
    try:
        result = get_share_store().share(user_id, relpaths, usernames, _known_usernames())
    except ValueError as exc:
        return _json_error(str(exc))
    images = [
        {"relpath": item["relpath"], "owner": username, "viewers": item["viewers"]}
        for item in result["shares"]
    ]
    return web.json_response({"ok": True, "images": images})


@routes.post("/usgromana/api/image-shares/revoke")
async def revoke_image_shares(request: web.Request) -> web.Response:
    user_id, username = _caller(request)
    if not user_id:
        return _json_error("Authentication required", 401)
    data = await _body(request)
    relpaths = data.get("relpaths") or []
    usernames = data.get("usernames") or []
    if isinstance(relpaths, str):
        relpaths = [relpaths]
    if isinstance(usernames, str):
        usernames = [usernames]
    try:
        result = get_share_store().revoke(user_id, relpaths, usernames)
    except ValueError as exc:
        return _json_error(str(exc))
    images = [
        {"relpath": item["relpath"], "owner": username, "viewers": item["viewers"]}
        for item in result["shares"]
    ]
    return web.json_response({"ok": True, "images": images})

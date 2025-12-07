# utils/watcher.py

import logging
from aiohttp import web

LOG = logging.getLogger("usgromana.watcher")

WORKFLOW_DENY_CODE = "WORKFLOW_SAVE_DENIED"


def create_error_watcher_middleware():
    """
    Middleware that:
      - Watches all responses
      - If a 403 occurs on /api/userdata/workflows*, tag it so the UI can react
      - Optionally log it
    """
    @web.middleware
    async def middleware(request: web.Request, handler):
        resp = await handler(request)

        # Only care about 403s
        if not isinstance(resp, web.Response) or resp.status != 403:
            return resp

        path = request.path or ""

        # Only touch workflow userdata endpoints
        if path.startswith("/api/userdata/workflows"):
            resp.headers["X-Usgromana-Error"] = WORKFLOW_DENY_CODE
            LOG.info(
                "[Watcher] Tagged workflow save denial: path=%s method=%s",
                path,
                request.method,
            )

        return resp

    return middleware


def register(app: web.Application):
    """
    Attach the watcher middleware to the app.
    Call this *after* access_control.create_usgromana_middleware()
    """
    app.middlewares.append(create_error_watcher_middleware())

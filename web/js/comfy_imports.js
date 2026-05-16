/**
 * ComfyUI frontend module paths (extension-relative + site-root fallbacks).
 * Centralizes paths so Comfy renames are updated in one place.
 */
export const COMFY_SCRIPT_PATHS = {
    app: ["../../scripts/app.js", "/scripts/app.js"],
    api: ["../../scripts/api.js", "/scripts/api.js"],
    ui: ["../../scripts/ui.js", "/scripts/ui.js"],
};

let _modulesPromise = null;

async function importFirst(paths, label) {
    let lastErr;
    for (const spec of paths) {
        try {
            return await import(spec);
        } catch (e) {
            lastErr = e;
        }
    }
    console.error(`[Usgromana] Failed to load Comfy ${label} module`, lastErr);
    throw lastErr;
}

/** Load app, api, and ui once (cached). */
export function loadComfyModules() {
    if (!_modulesPromise) {
        _modulesPromise = Promise.all([
            importFirst(COMFY_SCRIPT_PATHS.app, "app"),
            importFirst(COMFY_SCRIPT_PATHS.api, "api"),
            importFirst(COMFY_SCRIPT_PATHS.ui, "ui"),
        ]).then(([appMod, apiMod, uiMod]) => ({
            app: appMod.app,
            api: apiMod.api,
            ComfyDialog: uiMod.ComfyDialog,
            $el: uiMod.$el,
        }));
    }
    return _modulesPromise;
}

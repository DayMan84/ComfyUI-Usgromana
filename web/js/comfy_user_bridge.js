import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { installDenialToastWatcher } from "./denial_toasts.js";

/**
 * Align ComfyUI's Assets tab (and other comfy-user APIs) with the logged-in
 * Usgromana account so each user only sees their own output/input files.
 *
 * ComfyUI's Generated tab reads /api/jobs (prompt history), not /api/assets.
 * The server merges disk-backed outputs into that response; this patch is a
 * fallback if the UI requests history before middleware runs.
 */
let comfyUserId = null;

async function loadComfyUserId() {
    try {
        const res = await fetch("/usgromana/api/me", { credentials: "include" });
        if (!res.ok) {
            comfyUserId = null;
            return null;
        }
        const data = await res.json();
        comfyUserId = data.user_id || null;
        return comfyUserId;
    } catch (e) {
        console.warn("[Usgromana] Could not load user id for assets bridge:", e);
        comfyUserId = null;
        return null;
    }
}

function previewKey(preview) {
    if (!preview?.filename) return null;
    const subfolder = (preview.subfolder || "").replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
    return `${subfolder}\0${preview.filename}`;
}

function mergeGeneratedJobs(historyJobs, diskJobs) {
    const seen = new Set();
    const out = [];
    for (const job of historyJobs) {
        if (job?.status === "completed" && job.preview_output) {
            const key = previewKey(job.preview_output);
            if (key) seen.add(key);
        }
        out.push(job);
    }
    for (const job of diskJobs) {
        if (job?.status !== "completed" || !job.preview_output) continue;
        const key = previewKey(job.preview_output);
        if (key && seen.has(key)) continue;
        if (key) seen.add(key);
        out.push(job);
    }
    out.sort((a, b) => (b.create_time || 0) - (a.create_time || 0));
    return out;
}

function patchFetchApi() {
    if (!api?.fetchApi || api._usgromanaComfyUserPatched) {
        return;
    }

    const originalFetchApi = api.fetchApi.bind(api);

    api.fetchApi = async function (url, options = {}) {
        const uid = comfyUserId || (await loadComfyUserId());
        if (uid) {
            const headers = new Headers(options.headers || {});
            if (!headers.has("Comfy-User")) {
                headers.set("Comfy-User", uid);
            }
            options = { ...options, headers };
        }
        return originalFetchApi(url, options);
    };

    api._usgromanaComfyUserPatched = true;
}

function patchGetHistory() {
    if (!api?.getHistory || api._usgromanaHistoryPatched) {
        return;
    }

    const originalGetHistory = api.getHistory.bind(api);

    api.getHistory = async function (limit = 200, opts) {
        const offset = opts?.offset ?? 0;
        const history = await originalGetHistory(limit, opts);
        if (offset > 0 || !Array.isArray(history)) {
            return history;
        }
        try {
            const res = await fetch("/usgromana/api/generated-jobs", {
                credentials: "include",
            });
            if (!res.ok) {
                return history;
            }
            const data = await res.json();
            const diskJobs = Array.isArray(data?.jobs) ? data.jobs : [];
            if (!diskJobs.length) {
                return history;
            }
            const merged = mergeGeneratedJobs(history, diskJobs);
            console.log(
                `[Usgromana] Generated tab: merged ${diskJobs.length} disk image(s) into history (${merged.length} total)`
            );
            return merged.slice(0, limit);
        } catch (e) {
            console.warn("[Usgromana] Could not merge generated jobs:", e);
            return history;
        }
    };

    api._usgromanaHistoryPatched = true;
}

/**
 * ComfyUI frontend reads api.user / api.userId after /users; set from Usgromana session
 * so the built-in user picker is skipped when the server still exposes a user list.
 */
function applyComfyApiUser(uid) {
    if (!uid || !api) return;
    try {
        api.user = uid;
        api.userId = uid;
    } catch (_) {
        /* ignore */
    }
}

app.registerExtension({
    name: "Usgromana.ComfyUserBridge",
    async init() {
        const uid = await loadComfyUserId();
        if (uid) {
            applyComfyApiUser(uid);
            patchFetchApi();
            patchGetHistory();
        }
    },
    async setup() {
        installDenialToastWatcher();
        await loadComfyUserId();
        patchFetchApi();
        patchGetHistory();
        applyComfyApiUser(comfyUserId);
        console.log(
            "[Usgromana] Comfy user bridge active",
            comfyUserId ? `(user ${comfyUserId})` : "(guest / not signed in)"
        );
    },
});

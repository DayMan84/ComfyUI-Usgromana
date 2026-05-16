/**
 * Grouped access-denial toasts (workflow save, manager, etc.) with Clear all.
 */

const STACK_ID = "usgromana-denial-toast-stack";
const DEDUPE_MS = 2000;
const AUTO_DISMISS_MS = 8000;

const DENIAL_URL_HINTS = [
    "/api/userdata/workflows",
    "/extensions/comfyui-manager",
    "/api/manager",
    "/manager",
];

let _styleInjected = false;
const _entries = new Map();

function injectStyles() {
    if (_styleInjected) return;
    _styleInjected = true;
    const style = document.createElement("style");
    style.textContent = `
#${STACK_ID} {
    position: fixed;
    top: 16px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 100000;
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-width: min(420px, calc(100vw - 32px));
    pointer-events: none;
}
#${STACK_ID} .usgromana-denial-stack-header,
#${STACK_ID} .usgromana-denial-toast-item {
    pointer-events: auto;
}
.usgromana-denial-stack-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 8px 12px;
    border-radius: 10px;
    background: rgba(20, 20, 24, 0.92);
    border: 1px solid rgba(255,255,255,0.14);
    color: #f0f0f0;
    font-size: 12px;
    box-shadow: 0 6px 24px rgba(0,0,0,0.35);
}
.usgromana-denial-stack-header button {
    background: rgba(255,255,255,0.1);
    border: none;
    color: #fff;
    padding: 4px 10px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 11px;
}
.usgromana-denial-stack-header button:hover {
    background: rgba(255,255,255,0.18);
}
.usgromana-denial-toast-item {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 12px 14px;
    border-radius: 10px;
    background: rgba(30, 30, 30, 0.9);
    backdrop-filter: blur(6px);
    color: #fff;
    font-size: 13px;
    border: 1px solid rgba(255,255,255,0.12);
    box-shadow: 0 6px 30px rgba(0,0,0,0.35);
    opacity: 0;
    transform: translateY(-6px);
    transition: opacity 0.2s ease, transform 0.2s ease;
}
.usgromana-denial-toast-item.usgromana-denial-visible {
    opacity: 1;
    transform: translateY(0);
}
.usgromana-denial-toast-item .usgromana-denial-count {
    font-size: 11px;
    opacity: 0.75;
    margin-left: 4px;
}
.usgromana-denial-toast-item button.usgromana-denial-dismiss {
    background: rgba(255,255,255,0.08);
    border: none;
    width: 22px;
    height: 22px;
    border-radius: 6px;
    color: #fff;
    cursor: pointer;
    flex-shrink: 0;
}
`;
    document.head.appendChild(style);
}

function getStack() {
    injectStyles();
    let stack = document.getElementById(STACK_ID);
    if (!stack) {
        stack = document.createElement("div");
        stack.id = STACK_ID;
        document.body.appendChild(stack);
    }
    return stack;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = String(text ?? "");
    return div.innerHTML;
}

function categorizeUrl(url) {
    const u = (url || "").toLowerCase();
    if (u.includes("/api/userdata/workflows")) return "workflow";
    if (u.includes("comfyui-manager") || u.includes("/api/manager") || u.includes("/manager")) {
        return "manager";
    }
    return "access";
}

function entryKey(category, message) {
    return `${category}::${(message || "").trim().slice(0, 200)}`;
}

function renderStackHeader(stack) {
    let header = stack.querySelector(".usgromana-denial-stack-header");
    const count = _entries.size;
    if (count < 2) {
        header?.remove();
        return;
    }
    if (!header) {
        header = document.createElement("div");
        header.className = "usgromana-denial-stack-header";
        stack.insertBefore(header, stack.firstChild);
    }
    header.innerHTML = `
        <span><strong>${count}</strong> actions blocked</span>
        <button type="button" data-action="clear-all">Clear all</button>
    `;
    header.querySelector("[data-action='clear-all']").onclick = () => clearAllDenialToasts();
}

function removeEntry(key) {
    const entry = _entries.get(key);
    if (!entry) return;
    if (entry.timer) clearTimeout(entry.timer);
    entry.el?.remove();
    _entries.delete(key);
    const stack = document.getElementById(STACK_ID);
    if (stack) renderStackHeader(stack);
    if (_entries.size === 0) stack?.remove();
}

export function clearAllDenialToasts() {
    for (const key of [..._entries.keys()]) {
        removeEntry(key);
    }
}

/**
 * @param {{ message?: string, category?: string, title?: string }} opts
 */
export function notifyAccessDenied(opts = {}) {
    const message =
        opts.message ||
        "You are not allowed to perform this action with this account.";
    const category = opts.category || "access";
    const title = opts.title || "Action blocked";
    const key = entryKey(category, message);
    const now = Date.now();
    const stack = getStack();

    const existing = _entries.get(key);
    if (existing && now - existing.lastAt < DEDUPE_MS) {
        existing.count += 1;
        existing.lastAt = now;
        const countEl = existing.el.querySelector(".usgromana-denial-count");
        if (countEl) countEl.textContent = `(${existing.count}×)`;
        if (existing.timer) clearTimeout(existing.timer);
        existing.timer = setTimeout(() => removeEntry(key), AUTO_DISMISS_MS);
        renderStackHeader(stack);
        return;
    }

    const el = document.createElement("div");
    el.className = "usgromana-denial-toast-item";
    el.innerHTML = `
        <div style="font-size:17px;line-height:1;">⛔</div>
        <div style="flex:1;">
            <div style="font-weight:600;margin-bottom:2px;">${escapeHtml(title)}</div>
            <div style="opacity:0.9;">${escapeHtml(message)}<span class="usgromana-denial-count"></span></div>
        </div>
        <button type="button" class="usgromana-denial-dismiss" aria-label="Dismiss">✕</button>
    `;
    el.querySelector(".usgromana-denial-dismiss").onclick = () => removeEntry(key);

    stack.appendChild(el);
    requestAnimationFrame(() => el.classList.add("usgromana-denial-visible"));

    const timer = setTimeout(() => removeEntry(key), AUTO_DISMISS_MS);
    _entries.set(key, { el, count: 1, lastAt: now, timer });
    renderStackHeader(stack);
}

export async function extractDenialMessage(response) {
    try {
        const clone = response.clone();
        const ct = (clone.headers.get("content-type") || "").toLowerCase();
        if (ct.includes("application/json")) {
            const data = await clone.json();
            if (data && typeof data.error === "string") return data.error;
            if (data && typeof data.message === "string") return data.message;
        }
        const text = (await clone.text()).trim();
        if (text && text.length <= 400) return text;
    } catch (e) {
        console.debug("[usgromana] denial message parse failed:", e);
    }
    return null;
}

function isDenialUrl(url) {
    const u = (url || "").toLowerCase();
    return DENIAL_URL_HINTS.some((hint) => u.includes(hint));
}

/**
 * @param {{ shouldNotify?: (url: string, response: Response) => boolean }} options
 */
function defaultShouldNotify(url) {
    return isDenialUrl(url);
}

export function installDenialToastWatcher(options = {}) {
    if (options.shouldNotify) {
        window.__usgromanaDenialShouldNotify = options.shouldNotify;
    }
    if (window.fetch && window.fetch.__usgromanaDenialWrapped) {
        return;
    }

    const shouldNotify = (url, response) => {
        const fn = window.__usgromanaDenialShouldNotify || defaultShouldNotify;
        return fn(url, response);
    };

    const originalFetch = window.fetch.bind(window);

    async function wrappedFetch(input, init) {
        const response = await originalFetch(input, init);

        try {
            const url =
                typeof input === "string"
                    ? input
                    : input && input.url
                      ? input.url
                      : "";

            if (response.status === 403 && shouldNotify(url, response)) {
                let msg = await extractDenialMessage(response);
                if (!msg) {
                    if (url.toLowerCase().includes("/api/userdata/workflows")) {
                        msg =
                            "You are not allowed to save or delete workflows with this account.";
                    } else if (
                        url.toLowerCase().includes("manager") ||
                        url.toLowerCase().includes("comfyui-manager")
                    ) {
                        msg = "ComfyUI-Manager is not available for your role.";
                    } else {
                        msg = "Usgromana: Access Denied";
                    }
                }
                notifyAccessDenied({
                    message: msg,
                    category: categorizeUrl(url),
                });
            }
        } catch (e) {
            console.warn("[usgromana] denial toast watcher error:", e);
        }

        return response;
    }

    wrappedFetch.__usgromanaDenialWrapped = true;
    window.fetch = wrappedFetch;
}

window.UsgromanaDenialToasts = {
    notify: notifyAccessDenied,
    clearAll: clearAllDenialToasts,
};

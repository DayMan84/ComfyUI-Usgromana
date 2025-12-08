import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { ComfyDialog, $el } from "../../scripts/ui.js";

const GROUPS = ["admin", "power", "user", "guest"];
let currentUser = null;
let groupsConfig = {};

// Backend API endpoints (adjust if your backend uses different paths)
const IP_API_ENDPOINT = "/usgromana/api/ip-lists";
const USER_ENV_API_ENDPOINT = "/usgromana/api/user-env";

// --- 1. BLOCKING MAP (The Enforcer) ---
// If a user lacks permission for the Key, these CSS selectors are hidden via !important
const CSS_BLOCK_MAP = {
    // --- Core UI ---
    "ui_queue_button": ["#queue-button", ".queue-button", "button.queue-button"],
    "ui_batch_widget": [".comfy-menu-queue-batch"],
    "ui_extra_options": [".comfy-menu-queue-extra"],
    
    // --- Sidebar / Left Toolbar ---
    // Core & Common Extensions
    "ui_side_history": ["#comfy-view-history-button", "[title='History']", ".pi-history"], // Often clock icon
    "ui_side_queue": ["#comfy-view-queue-button", "[title='Queue']", ".pi-list"], 
    "ui_side_assets": [
        "[title='Assets']", 
        ".pi-folder",                 // Common icon for assets
        "#comfyui-browser-button",    // ComfyUI-Browser
        ".comfy-assets-tab",
        "button.assets-tab-button",
        ".assets-tab-button",
        ".assets-tab-button .side-bar-button-label"
    ],
    "ui_side_templates": [
        "[title='Templates']", 
        ".pi-copy",                   // Common icon for templates
        "#node-templates-button",     // Node Templates
        ".comfy-templates-tab",
        "button.templates-tab-button",
        ".templates-tab-button",
        ".templates-tab-button .side-bar-button-label"
    ],
    
    // --- Standard Menus (New Vue/Prime UI + legacy ids) ---
    // NOTE:
    // - We treat "Save", "Save As", "Export", and "Export (API)" all as "ui_menu_save"
    //   because they all modify or export workflows.
    // - "Open" is controlled by ui_menu_load.

    "ui_menu_save": [
        // Old ComfyUI top-bar save button (if still present anywhere)
        "#comfy-save-button",
        // New File menu entries
        "li.p-tieredmenu-item[aria-label='Save']",
        "li.p-tieredmenu-item[aria-label='Save As']",
        "li.p-tieredmenu-item[aria-label='Export']",
        "li.p-tieredmenu-item[aria-label='Export (API)']"
    ],
    "ui_menu_load": [
        // Old ComfyUI load button
        "#comfy-load-button",
        // New "Open" menu entry in the File menu
        "li.p-tieredmenu-item[aria-label='Open']"
    ],
    "ui_menu_refresh": ["#comfy-refresh-button"],

    // --- Workflow breadcrumb (Graph title dropdown) ---
    "ui_workflow_breadcrumb": [".subgraph-breadcrumb"],

    "ui_menu_clipspace": ["#comfy-clipspace-button"],
    "ui_menu_clear": ["#comfy-clear-button"],
    "ui_menu_manager": [
        ".comfyui-manager-menu-btn", 
        "button.comfyui-manager-menu-btn"
    ],
    "ui_menu_extensions": [
        "li.p-tieredmenu-item[aria-label='Manage Extensions']",
        "li.p-tieredmenu-item[aria-label='Manage Extensions'] *"
    ],
    "ui_menu_templates": [
        "li.p-tieredmenu-item[aria-label='Browse Templates']",
        "li.p-tieredmenu-item[aria-label='Browse Templates'] *"
    ],

    // --- Extensions (Hotbars, Overlays, & Settings Menu) ---
    "settings_extension": [
        "li[aria-label='Extension']",
        "li.p-listbox-option[aria-label='Extension']"
    ],
    "settings_user": [
        "li[aria-label='User']",
        "li.p-listbox-option[aria-label='User']"
    ],
    "settings_keybinding": [
        "li[aria-label='Keybinding']",
        "li.p-listbox-option[aria-label='Keybinding']"
    ],
    "settings_appearance": [
        "li[aria-label='Appearance']",
        "li.p-listbox-option[aria-label='Appearance']"
    ],
    "settings_litegraph": [
        "li[aria-label='Lite Graph']",
        "li.p-listbox-option[aria-label='Lite Graph']"
    ],
    "Serttings_3D": [
        "li[aria-label='3D']",
        "li.p-listbox-option[aria-label='3D']"
    ],
    "settings_maskeditor": [
        "li[aria-label='Mask Editor']",
        "li.p-listbox-option[aria-label='Mask Editor']"
    ],
    
    // iTools
    "settings_itools": [
        ".itools-floating-bar", 
        ".itools-menu-btn",
        ".itools-panel",
        "[id*='itools']"
    ],
    // Crystools
    "settings_crystools": [
        "#crystools-root",
        ".crystools-nav-bar",
        ".crystools-save-button",
        "[title^='Crystools']"
    ],
    // rgthree
    "settings_rgthree": [
        ".rgthree-menu-btn",
        ".rgthree-context-menu"
    ],
    // Gallery
    "settings_gallery": [
        ".gallery-container",
        "#gallery-button"
    ],
    // Impact Pack
    "settings_impact": [
        "#impact-pack-button" 
    ]
};

// --- 2. MODAL CSS (The Look & Feel) ---
const ADMIN_STYLES = `
/* Overlay Backdrop */
.usgromana-modal-overlay {
    position: fixed;
    inset: 0;
    width: 100vw;
    height: 100vh;
    /* a bit more transparent so the app shows through */
    background: radial-gradient(circle at top, rgba(0,0,0,0.75), rgba(0,0,0,0.92));
    backdrop-filter: blur(6px);
    z-index: 10000;
    display: flex;
    align-items: center;
    justify-content: center;
}

/* Main Window */
.usgromana-modal {
    position: relative;
    width: 960px;
    max-width: 96vw;
    height: 720px;
    max-height: 92vh;
    /* slightly more transparent card */
    background: rgba(12, 12, 16, 0.92);
    color: #f5f5f7;
    display: flex;
    flex-direction: column;
    border-radius: 12px;
    overflow: hidden;
    box-shadow:
        0 22px 60px rgba(0,0,0,0.95),
        0 0 0 1px rgba(255,255,255,0.08);
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

/* Large transparent logo in the background */
.usgromana-modal::before {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    opacity: 0.06;  /* tweak if too bright/dim */
    background-image:
        url("/usgromana-web/assets/light_logo_transparent.png"),
        url("/usgromana/assets/light_logo_transparent.png");
    background-repeat: no-repeat;
    background-position: center 35%;
    background-size: 420px auto;
    mix-blend-mode: screen;
    z-index: 0;
}

/* Small logo badge in the top-right corner */
.usgromana-modal::after {
    content: "";
    position: absolute;
    top: 10px;
    right: 18px;
    width: 120px;
    height: 40px;
    pointer-events: none;
    background-image:
        url("/usgromana-web/assets/light_logo_transparent.png"),
        url("/usgromana/assets/light_logo_transparent.png");
    background-repeat: no-repeat;
    background-position: right center;
    background-size: contain;
    opacity: 0.4;
    z-index: 1;
}

/* Header */
.usgromana-modal-header {
    padding: 14px 20px;
    background: linear-gradient(
        to right,
        rgba(255,255,255,0.05),
        rgba(255,255,255,0.02)
    );
    border-bottom: 1px solid rgba(255,255,255,0.14);
    display: flex;
    justify-content: space-between;
    align-items: center;
    z-index: 2;
    position: relative;
}
.usgromana-modal-title {
    font-size: 17px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #ffffff;
}
.usgromana-modal-subtitle {
    font-size: 12px;
    opacity: 0.9;
    color: #d0d0d0;
}
.usgromana-modal-close {
    cursor: pointer;
    font-size: 20px;
    color: #e0e0e0;
    background: none;
    border: none;
    transition: 0.16s ease;
    padding: 2px 6px;
    border-radius: 999px;
}
.usgromana-modal-close:hover {
    color: #ffffff;
    background: rgba(255,255,255,0.12);
    transform: translateY(-1px);
}

/* Body & Tabs */
.usgromana-modal-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: radial-gradient(
        circle at top left,
        rgba(255,255,255,0.04),
        rgba(0,0,0,0.96)
    );
    z-index: 2;
    position: relative;
}
.usgromana-tabs {
    display: flex;
    background: #181b22;
    padding: 0 16px;
    border-bottom: 1px solid rgba(255,255,255,0.14);
    gap: 2px;
}
.usgromana-tab {
    padding: 10px 20px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 600;
    color: #c5c8d3;
    border-bottom: 2px solid transparent;
    transition: 0.16s ease;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.usgromana-tab:hover {
    color: #ffffff;
    background: rgba(255,255,255,0.06);
}
.usgromana-tab.active {
    color: #ffffff;
    border-bottom-color: var(--p-button-primary-bg, #3b82f6);
    background: rgba(59,130,246,0.18);
}

/* Content Area */
.usgromana-content {
    flex: 1;
    padding: 10px 0 0;
    overflow-y: auto;
    display: none;
}
.usgromana-content.active {
    display: block;
}

/* Tables */
.usgromana-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}
.usgromana-table th {
    text-align: left;
    padding: 12px 18px;
    border-bottom: 1px solid rgba(255,255,255,0.22);
    position: sticky;
    top: 0;
    z-index: 10;
    background: #171923;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.10em;
    color: #f9fafb;  /* bright */
}
.usgromana-table td {
    padding: 10px 18px;
    border-bottom: 1px solid rgba(255,255,255,0.10);
    vertical-align: middle;
    color: #e5e7f3;  /* brighter row text */
    font-size: 13px;
}
.usgromana-table tr:nth-child(even) td {
    background: rgba(255,255,255,0.02);
}
.usgromana-table tr:hover td {
    background: rgba(59,130,246,0.20);
}

/* Table Sections */
.usgromana-section-row td {
    background: #151821;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    padding: 22px 18px 10px;
    color: #f9fafb;
    font-size: 11px;
    border-bottom: 2px solid rgba(255,255,255,0.24);
}

/* Checkbox cell */
.usgromana-check-cell {
    text-align: center;
    width: 80px;
    border-left: 1px solid rgba(255,255,255,0.15);
}

/* Buttons */
.usgromana-btn {
    background: var(--p-button-primary-bg, #3b82f6);
    color: var(--p-button-primary-text, #ffffff);
    border: 1px solid rgba(255,255,255,0.24);
    padding: 7px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
    font-size: 12px;
    transition: 0.16s ease;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
}
.usgromana-btn:hover {
    opacity: 0.97;
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(0,0,0,0.7);
}
.usgromana-btn.secondary {
    background: rgba(255,255,255,0.04);
    color: #e5e7f3;
}
.usgromana-btn.danger {
    background: #7a2525;
    border-color: #aa3a3a;
}
.usgromana-btn.usgromana-btn-danger {
    background: #8b1f2f;
    border: 1px solid #b03a4a;
}

.usgromana-btn.usgromana-btn-danger:hover {
    background: #b03a4a;
    border-color: #d14f5d;
}

/* Launcher button in the Comfy Settings panel */
.usgromana-launch-btn {
    width: 100%;
    padding: 10px;
    font-weight: 600;
    border-radius: 8px;
    margin-top: 6px;

    /* Strong contrast on BOTH light and dark settings panels */
    background: #111827;                 /* dark slate */
    color: #f9fafb;
    border: 1px solid #1f2937;
    cursor: pointer;
    box-shadow: 0 4px 10px rgba(0,0,0,0.35);
    text-align: center;
}

.usgromana-launch-btn:hover {
    background: #1d4ed8;                 /* blue on hover */
    border-color: #1e40af;
    color: #ffffff;
    box-shadow: 0 6px 16px rgba(0,0,0,0.45);
}

/* Small info text */
.usgromana-note {
    font-size: 12px;
    opacity: 0.95;
    color: #d3d3dd;
}

/* Flex layouts */
.usgromana-row {
    display: flex;
    gap: 12px;
    align-items: flex-start;
}
.usgromana-row-space {
    display: flex;
    gap: 12px;
    justify-content: space-between;
    align-items: center;
}
.usgromana-col {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

/* Inputs / textareas */
.usgromana-textarea,
.usgromana-input {
    background: #181a23;
    color: #f5f5f7;
    border-radius: 6px;
    border: 1px solid rgba(255,255,255,0.28);
    padding: 6px 8px;
    font-size: 12px;
    resize: vertical;
}
.usgromana-textarea {
    min-height: 140px;
    width: 100%;
    font-family: monospace;
}
.usgromana-select {
    background: #181a23;
    color: #f5f5f7;
    border-radius: 6px;
    border: 1px solid rgba(255,255,255,0.28);
    padding: 5px 8px;
    font-size: 12px;
}

/* Env file list / cards */
.usgromana-card {
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,0.18);
    background: #13141c;
    padding: 12px 14px;
    margin: 4px 0 10px;
}
.usgromana-card-header {
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 4px;
    color: #ffffff;
}
.usgromana-chip {
    display: inline-flex;
    padding: 2px 7px;
    border-radius: 999px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    border: 1px solid rgba(255,255,255,0.35);
}
.usgromana-file-list {
    max-height: 240px;
    overflow-y: auto;
    font-family: monospace;
    font-size: 11px;
    padding: 6px 8px;
    border-radius: 6px;
    border: 1px solid rgba(255,255,255,0.25);
    background: #101119;
    color: #f5f5f7;
}

/* Toast */
.usgromana-toast {
    position: fixed;
    top: 18px;
    left: 50%;
    transform: translateX(-50%);
    padding: 10px 16px;
    background: rgba(0,0,0,0.92);
    color: #f5f5f7;
    border-radius: 999px;
    font-size: 12px;
    z-index: 11000;
    box-shadow: 0 10px 30px rgba(0,0,0,0.8);
    border: 1px solid rgba(255,255,255,0.3);
}

/* Enforcement */
.usgromana-blocked-item {
    display: none !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
`;
// --- DATA HELPERS ---
async function getData(endpoint) {
    try {
        const res = await api.fetchApi(endpoint);
        if (res.status === 200) return await res.json();
    } catch (e) { console.error(e); }
    return null;
}

function getSanitizedId(text) {
    if (!text) return "";
    return "settings_" + text.trim().toLowerCase().replace(/[^a-z0-9]/g, "");
}

// --- 3. ADMIN DIALOG CLASS ---
class usgromanaDialog extends ComfyDialog {
    constructor() {
        super();
        this.overlay = $el("div.usgromana-modal-overlay");
        this.element = $el("div.usgromana-modal");
    }

    async show() {
        this.overlay.appendChild(this.element);
        document.body.appendChild(this.overlay);
        this.element.innerHTML = `<div style="padding:50px; text-align:center;">Loading System Configuration...</div>`;
        
        // Fetch fresh data
        const [me, groups, users] = await Promise.all([
            getData("/usgromana/api/me"),
            getData("/usgromana/api/groups"),
            getData("/usgromana/api/users")
        ]);

        currentUser = me;
        groupsConfig = groups?.groups || {};
        const usersList = users?.users || [];

        // Admin Guard
        if (!currentUser || !currentUser.is_admin) {
            this.element.innerHTML = `
                <div style="padding:40px; text-align:center; color:#ff6b6b;">
                    <h2>Access Denied</h2>
                    <p>Administrative privileges are required to modify system policies.</p>
                    <br><button id='s-close-btn' class='usgromana-btn'>Close</button>
                </div>`;
            this.element.querySelector("#s-close-btn").onclick = () => this.close();
            return;
        }

        // Render Layout
        this.element.innerHTML = `
            <div class="usgromana-modal-header">
                <span class="usgromana-modal-title">usgromana Security Policy</span>
                <button class="usgromana-modal-close">✕</button>
            </div>
            <div class="usgromana-modal-body">
                <div class="usgromana-tabs">
                    <div class="usgromana-tab active" data-tab="users">Users & Roles</div>
                    <div class="usgromana-tab" data-tab="perms">Permissions & UI</div>
                    <div class="usgromana-tab" data-tab="ip">IP Rules</div>
                    <div class="usgromana-tab" data-tab="env">User Env</div>
                </div>
                <div class="usgromana-content active" id="usgromana-tab-users"></div>
                <div class="usgromana-content" id="usgromana-tab-perms"></div>
                <div class="usgromana-content" id="usgromana-tab-ip"></div>
                <div class="usgromana-content" id="usgromana-tab-env"></div>
            </div>
        `;

        // Bindings
        this.element.querySelector(".usgromana-modal-close").onclick = () => this.close();
        this.overlay.onclick = (e) => { if (e.target === this.overlay) this.close(); };

        const tabs = this.element.querySelectorAll(".usgromana-tab");
        tabs.forEach(t => t.onclick = () => {
            tabs.forEach(x => x.classList.remove("active"));
            this.element.querySelectorAll(".usgromana-content").forEach(c => c.classList.remove("active"));
            t.classList.add("active");
            this.element.querySelector(`#usgromana-tab-${t.dataset.tab}`).classList.add("active");
        });

        // Fill Data
        this.renderUsers(usersList, this.element.querySelector("#usgromana-tab-users"));
        this.renderPerms(this.element.querySelector("#usgromana-tab-perms"));
        await this.renderIpRules(this.element.querySelector("#usgromana-tab-ip"));
        this.renderUserEnv(this.element.querySelector("#usgromana-tab-env"), usersList);
    }

    close() { this.overlay.remove(); }

renderUsers(list, container) {
    const currentName = currentUser?.username || null;
    const self = this;

    let html = `
        <table class="usgromana-table">
            <thead>
                <tr>
                    <th>User Account</th>
                    <th>Assigned Group</th>
                    <th style="text-align:center;width:120px;">SFW Check</th>
                    <th style="text-align:right;width:180px;">Actions</th>
                </tr>
            </thead>
            <tbody>
    `;

    list.forEach(u => {
        const grp = (u.groups && u.groups.length) ? u.groups[0] : "user";
        const uname = u.username || "unknown";
        const isSelf = currentName && uname === currentName;
        const isGuest = uname.toLowerCase() === "guest";

        // NEW: per-user SFW flag; default ON if undefined
        const sfwEnabled = (u.sfw_check !== false);

        let actionsHtml = `
            <button class="usgromana-btn btn-save" data-user="${uname}">
                Save Changes
            </button>
        `;

        // Don't allow deleting yourself or the guest account
        if (!isSelf && !isGuest) {
            actionsHtml += `
                <button class="usgromana-btn usgromana-btn-danger btn-delete" data-user="${uname}">
                    Delete
                </button>
            `;
        }

        html += `
            <tr>
                <td><strong>${uname}</strong></td>
                <td>
                    <select
                        class="usgromana-role-select"
                        data-user="${uname}"
                        style="background:var(--comfy-input-bg); color:var(--input-text); border:1px solid #555; padding:6px 10px; border-radius:4px; width: 150px;"
                    >
                        ${GROUPS.map(g => `
                            <option value="${g}" ${g === grp ? "selected" : ""}>
                                ${g.toUpperCase()}
                            </option>
                        `).join("")}
                    </select>
                </td>
                <td style="text-align:center">
                    <input
                        type="checkbox"
                        class="usgromana-sfw-toggle"
                        data-user="${uname}"
                        ${sfwEnabled ? "checked" : ""}
                    />
                </td>
                <td style="text-align:right">
                    ${actionsHtml}
                </td>
            </tr>
        `;
    });

    html += `</tbody></table>`;
    container.innerHTML = html;

    // --- Save handler per user ---
    container.querySelectorAll(".btn-save").forEach(btn => {
        btn.onclick = async () => {
            const u = btn.dataset.user;
            const g = container.querySelector(`select[data-user="${u}"]`).value;

            const sfwCheckbox = container.querySelector(`.usgromana-sfw-toggle[data-user="${u}"]`);
            const sfw = sfwCheckbox ? sfwCheckbox.checked : true;

            btn.innerText = "Saving...";
            try {
                await api.fetchApi(`/usgromana/api/users/${u}`, {
                    method: "PUT",
                    body: JSON.stringify({
                        groups: [g],
                        sfw_check: sfw,
                    }),
                });
                btn.innerText = "Saved";
            } catch (e) {
                console.error("[usgromana] Failed to update user:", e);
                btn.innerText = "Error";
            }
            setTimeout(() => (btn.innerText = "Save Changes"), 1000);
        };
    });

    // --- Delete handler per user (unchanged logic) ---
    container.querySelectorAll(".btn-delete").forEach(btn => {
        btn.onclick = async () => {
            const u = btn.dataset.user;
            const confirmed = window.confirm(
                `Are you sure you want to delete the user "${u}"?\nThis cannot be undone.`
            );
            if (!confirmed) return;

            btn.disabled = true;
            const originalText = btn.innerText;
            btn.innerText = "Deleting...";

            try {
                const res = await api.fetchApi(`/usgromana/api/users/${u}`, {
                    method: "DELETE",
                });

                if (res.status === 200) {
                    const usersData = await getData("/usgromana/api/users");
                    const usersList = usersData?.users || [];
                    self.renderUsers(usersList, container);
                } else {
                    let msg = "Failed to delete user.";
                    try {
                        const err = await res.json();
                        if (err && err.error) msg = err.error;
                    } catch {}
                    window.alert(msg);
                    btn.disabled = false;
                    btn.innerText = originalText;
                }
            } catch (e) {
                console.error("[usgromana] Failed to delete user:", e);
                window.alert("Unexpected error while deleting user.");
                btn.disabled = false;
                btn.innerText = originalText;
            }
        };
    });
}

        async renderIpRules(container) {
        container.innerHTML = `
            <div class="usgromana-section">
                <h3>IP Whitelist & Blacklist</h3>
                <p>
                    Configure IP-based access rules. Whitelisted IPs are always allowed,
                    blacklisted IPs are always denied (before other checks).
                </p>
                <div class="usgromana-row">
                    <div>
                        <label class="usgromana-field-label">
                            Whitelist (one IP or CIDR per line)
                        </label>
                        <textarea class="usgromana-textarea" id="usgromana-ip-whitelist"></textarea>
                    </div>
                    <div>
                        <label class="usgromana-field-label">
                            Blacklist (one IP or CIDR per line)
                        </label>
                        <textarea class="usgromana-textarea" id="usgromana-ip-blacklist"></textarea>
                    </div>
                </div>
                <div style="display:flex; justify-content:flex-end; gap:8px; margin-top:8px;">
                    <button class="usgromana-btn secondary" id="usgromana-ip-refresh">Reload</button>
                    <button class="usgromana-btn" id="usgromana-ip-save">Save Rules</button>
                </div>
            </div>
        `;

        const wlEl = container.querySelector("#usgromana-ip-whitelist");
        const blEl = container.querySelector("#usgromana-ip-blacklist");
        const refreshBtn = container.querySelector("#usgromana-ip-refresh");
        const saveBtn = container.querySelector("#usgromana-ip-save");

        async function loadIpConfig() {
            const data = await getData(IP_API_ENDPOINT);
            const whitelist = (data?.whitelist || []).join("\\n");
            const blacklist = (data?.blacklist || []).join("\\n");
            wlEl.value = whitelist;
            blEl.value = blacklist;
        }

        await loadIpConfig();

        refreshBtn.onclick = () => loadIpConfig();

        saveBtn.onclick = async () => {
            const whitelist = wlEl.value
                .split(/\\r?\\n/)
                .map(l => l.trim())
                .filter(l => l.length > 0);
            const blacklist = blEl.value
                .split(/\\r?\\n/)
                .map(l => l.trim())
                .filter(l => l.length > 0);

            saveBtn.disabled = true;
            saveBtn.textContent = "Saving...";
            try {
                await api.fetchApi(IP_API_ENDPOINT, {
                    method: "PUT",
                    body: JSON.stringify({ whitelist, blacklist }),
                });
                saveBtn.textContent = "Saved";
                setTimeout(() => (saveBtn.textContent = "Save Rules"), 1200);
            } catch (e) {
                console.error("[usgromana] Failed to save IP rules:", e);
                saveBtn.textContent = "Error";
                setTimeout(() => (saveBtn.textContent = "Save Rules"), 1500);
            } finally {
                saveBtn.disabled = false;
            }
        };
    }

renderUserEnv(container, usersList) {
    const users = usersList || [];

    const userOptions = users
        .map(u => {
            const name = u.username || "unknown";
            return `<option value="${name}">${name}</option>`;
        })
        .join("");

    container.innerHTML = `
        <div class="usgromana-section">
            <h3>User Environment & Folders</h3>
            <p>
                Manage per-user environment folders created by <code>user_env.py</code>.
                You can inspect files, purge cached folders, delete individual files,
                and mark a user's folder as the active Gallery root.
            </p>

            <div class="usgromana-row">
                <div>
                    <label class="usgromana-field-label">User</label>
                    <select id="usgromana-env-user" class="usgromana-select">
                        ${userOptions}
                    </select>
                </div>
                <div style="display:flex; align-items:flex-end; gap:8px; justify-content:flex-end;">
                    <button class="usgromana-btn secondary" id="usgromana-env-list">List Files</button>
                    <button class="usgromana-btn danger" id="usgromana-env-purge">Purge Folders</button>
                </div>
            </div>

            <div class="usgromana-row" style="align-items:center; margin-top:4px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <input type="checkbox" id="usgromana-env-gallery-toggle" />
                    <label for="usgromana-env-gallery-toggle">
                        Use this user's folder as Gallery root
                    </label>
                </div>
            </div>

            <div style="margin-top:12px;">
                <label class="usgromana-field-label">Folder Contents / Status</label>
                <textarea id="usgromana-env-output" class="usgromana-textarea" readonly></textarea>
            </div>

            <div class="usgromana-row" style="margin-top:8px; align-items:flex-end; gap:8px;">
                <div style="flex:1;">
                    <label class="usgromana-field-label">Delete Single File</label>
                    <select id="usgromana-env-file" class="usgromana-select">
                        <option value="">(no files loaded yet)</option>
                    </select>
                </div>
                <button class="usgromana-btn danger" id="usgromana-env-delete">Delete File</button>
            </div>
        </div>

        <div class="usgromana-section" style="margin-top:16px;">
            <h3>Workflow Management</h3>
            <p>
                Promote a user's workflow into the global/default workflow list
                so it becomes visible to all users.
            </p>

            <div class="usgromana-row">
                <div>
                    <label class="usgromana-field-label">User</label>
                    <select id="usgromana-wf-user" class="usgromana-select">
                        ${userOptions}
                    </select>
                </div>
                <div style="flex:1;">
                    <label class="usgromana-field-label">Workflow</label>
                    <select id="usgromana-wf-select" class="usgromana-select">
                        <option value="">(load workflows...)</option>
                    </select>
                </div>
                <div style="display:flex; align-items:flex-end; gap:8px;">
                    <button class="usgromana-btn secondary" id="usgromana-wf-load">Load Workflows</button>
                    <button class="usgromana-btn primary" id="usgromana-wf-promote">Promote to Default</button>
                </div>
            </div>
            <div style="margin-top:6px; display:flex; align-items:center; gap:8px;">
                <input type="checkbox" id="usgromana-wf-delete-source" />
                <label for="usgromana-wf-delete-source">
                    Remove from this user's workflow folder after promotion
                </label>
            </div>
            <div style="margin-top:6px;">
                <small id="usgromana-wf-status" class="usgromana-muted"></small>
            </div>
        </div>
    `;

    const userSelect = container.querySelector("#usgromana-env-user");
    const listBtn = container.querySelector("#usgromana-env-list");
    const purgeBtn = container.querySelector("#usgromana-env-purge");
    const galleryToggle = container.querySelector("#usgromana-env-gallery-toggle");
    const output = container.querySelector("#usgromana-env-output");
    const fileSelect = container.querySelector("#usgromana-env-file");
    const deleteBtn = container.querySelector("#usgromana-env-delete");

    const wfUserSelect = container.querySelector("#usgromana-wf-user");
    const wfSelect = container.querySelector("#usgromana-wf-select");
    const wfLoadBtn = container.querySelector("#usgromana-wf-load");
    const wfPromoteBtn = container.querySelector("#usgromana-wf-promote");
    const wfDeleteSource = container.querySelector("#usgromana-wf-delete-source");
    const wfStatus = container.querySelector("#usgromana-wf-status");

    let envFiles = [];

    function getSelectedUser() {
        return userSelect?.value || null;
    }

    function getWorkflowUser() {
        return wfUserSelect?.value || getSelectedUser() || null;
    }

    function populateEnvFileOptions(files) {
        envFiles = files || [];
        if (!fileSelect) return;

        fileSelect.innerHTML = "";

        if (!envFiles.length) {
            fileSelect.innerHTML = `<option value="">(no files)</option>`;
            return;
        }

        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "(select a file...)";
        fileSelect.appendChild(placeholder);

        envFiles.forEach(path => {
            const opt = document.createElement("option");
            opt.value = path;
            opt.textContent = path;
            fileSelect.appendChild(opt);
        });
    }

    async function refreshStatus() {
        const user = getSelectedUser();
        if (!user) return;
        output.value = "Loading status...";
        try {
            const res = await api.fetchApi(USER_ENV_API_ENDPOINT, {
                method: "POST",
                body: JSON.stringify({ action: "status", user }),
            });
            if (res.status === 200) {
                const data = await res.json();
                galleryToggle.checked = !!data.is_gallery_root;
                const files = data.files || [];
                populateEnvFileOptions(files);
                output.value =
                    (data.message || "") +
                    (files.length
                        ? "\n\nFiles:\n" + files.join("\n")
                        : files.length === 0
                        ? "\n\n(no files reported)"
                        : "");
            } else {
                output.value = "Error loading status: " + res.status;
            }
        } catch (e) {
            console.error("[usgromana] env status error:", e);
            output.value = "Error loading status. See console.";
        }
    }

    userSelect.onchange = () => {
        if (wfUserSelect) wfUserSelect.value = userSelect.value;
        refreshStatus();
    };

    listBtn.onclick = async () => {
        const user = getSelectedUser();
        if (!user) return;
        output.value = "Listing files...";
        try {
            const res = await api.fetchApi(USER_ENV_API_ENDPOINT, {
                method: "POST",
                body: JSON.stringify({ action: "list", user }),
            });
            if (res.status === 200) {
                const data = await res.json();
                const files = data.files || [];
                populateEnvFileOptions(files);
                output.value = files.length
                    ? files.join("\n")
                    : "(no files found)";
            } else {
                output.value = "Error listing files: " + res.status;
            }
        } catch (e) {
            console.error("[usgromana] env list error:", e);
            output.value = "Error listing files. See console.";
        }
    };

    deleteBtn.onclick = async () => {
        const user = getSelectedUser();
        const file = fileSelect?.value;
        if (!user || !file) return;
        output.value = `Deleting '${file}'...`;
        try {
            const res = await api.fetchApi(USER_ENV_API_ENDPOINT, {
                method: "POST",
                body: JSON.stringify({ action: "delete_file", user, file }),
            });
            const data = await res.json();
            if (res.status === 200) {
                output.value = data.message || `Deleted '${file}'.`;
            } else {
                output.value = data.error || `Error deleting file: ${res.status}`;
            }
        } catch (e) {
            console.error("[usgromana] env delete_file error:", e);
            output.value = "Error deleting file. See console.";
        } finally {
            refreshStatus();
        }
    };

    purgeBtn.onclick = async () => {
        const user = getSelectedUser();
        if (!user) return;
        purgeBtn.disabled = true;
        output.value = "Purging...";
        try {
            const res = await api.fetchApi(USER_ENV_API_ENDPOINT, {
                method: "POST",
                body: JSON.stringify({ action: "purge", user }),
            });
            if (res.status === 200) {
                const data = await res.json();
                output.value = data.message || "Purge completed.";
            } else {
                output.value = "Error purging folders: " + res.status;
            }
        } catch (e) {
            console.error("[usgromana] env purge error:", e);
            output.value = "Error purging folders. See console.";
        } finally {
            purgeBtn.disabled = false;
            refreshStatus();
        }
    };

    galleryToggle.onchange = async () => {
        const user = getSelectedUser();
        if (!user) return;
        const enable = galleryToggle.checked;

        try {
            const res = await api.fetchApi(USER_ENV_API_ENDPOINT, {
                method: "POST",
                body: JSON.stringify({
                    action: "set_gallery_root",
                    user,
                    enable,
                }),
            });
            if (res.status === 200) {
                const data = await res.json();
                output.value = data.message || "Gallery root updated.";
            } else {
                output.value = "Error updating gallery root: " + res.status;
            }
        } catch (e) {
            console.error("[usgromana] env gallery toggle error:", e);
            output.value = "Error updating gallery root. See console.";
        }
    };

    // --- Workflow admin handlers ---

    wfUserSelect.onchange = () => {
        wfStatus.textContent = "";
        wfSelect.innerHTML = '<option value="">(load workflows...)</option>';
    };

    wfLoadBtn.onclick = async () => {
        const user = getWorkflowUser();
        if (!user) return;
        wfStatus.textContent = "Loading workflows...";
        wfSelect.innerHTML = '<option value="">(loading...)</option>';

        try {
            const res = await api.fetchApi(USER_ENV_API_ENDPOINT, {
                method: "POST",
                body: JSON.stringify({
                    action: "list_workflows",
                    user,
                }),
            });
            if (res.status === 200) {
                const data = await res.json();
                const workflows = data.workflows || [];
                wfSelect.innerHTML = "";

                if (!workflows.length) {
                    wfSelect.innerHTML =
                        '<option value="">(no workflows)</option>';
                } else {
                    workflows.forEach((wf) => {
                        const opt = document.createElement("option");
                        opt.value = wf;
                        opt.textContent = wf;
                        wfSelect.appendChild(opt);
                    });
                }

                wfStatus.textContent = `Found ${workflows.length} workflow(s) for ${user}.`;
            } else {
                wfStatus.textContent =
                    "Error loading workflows: " + res.status;
            }
        } catch (e) {
            console.error("[usgromana] list_workflows error:", e);
            wfStatus.textContent =
                "Error loading workflows. See console.";
        }
    };

    wfPromoteBtn.onclick = async () => {
        const user = getWorkflowUser();
        const workflow = wfSelect?.value;
        if (!user || !workflow) return;
        const delete_source = !!(wfDeleteSource && wfDeleteSource.checked);
        wfStatus.textContent = `Promoting '${workflow}'...`;

        try {
            const res = await api.fetchApi(USER_ENV_API_ENDPOINT, {
                method: "POST",
                body: JSON.stringify({
                    action: "promote_workflow",
                    user,
                    workflow,
                    delete_source,
                }),
            });
            const data = await res.json();
            if (res.status === 200) {
                wfStatus.textContent =
                    data.message || "Workflow promoted to defaults.";
                // If we deleted the source, refresh the list
                if (delete_source) {
                    wfLoadBtn.onclick();
                }
            } else {
                wfStatus.textContent =
                    data.error ||
                    "Error promoting workflow: " + res.status;
            }
        } catch (e) {
            console.error("[usgromana] promote_workflow error:", e);
            wfStatus.textContent =
                "Error promoting workflow. See console.";
        }
    };

    // Initial sync + status
    if (userSelect && wfUserSelect) {
        wfUserSelect.value = userSelect.value;
    }
    if (users.length > 0) {
        refreshStatus();
    }
}

    renderPerms(container) {
        // --- SCANNER: Find all Settings Categories ---
        const categories = new Set();
        
        // 1. Scan app.extensions
        if (app.extensions) app.extensions.forEach(e => { if(e.name) categories.add(e.name); });
        
        // 2. Scan Settings (Sidebar Buttons)
        if (app.ui.settings.settings) {
            const items = (app.ui.settings.settings instanceof Map) ? Array.from(app.ui.settings.settings.values()) : Object.values(app.ui.settings.settings);
            items.forEach(s => {
                let c = s.category;
                if(Array.isArray(c)) c = c[0];
                if(!c && s.id) c = s.id.split(".")[0];
                if(c) categories.add(c);
            });
        }
        
        // 3. Explicit Whitelist (Ensure these appear even if scanner misses them)
        [
            "User", "Comfy", "LiteGraph", "Appearance", "Extension", 
            "3D", "Mask Editor", "Keybinding", "About",
            "iTools", "Crystools", "rgthree", "Gallery", "Impact"
        ].forEach(c => categories.add(c));
        
        // Clean exclusions
        categories.delete("usgromana"); 
        categories.delete("usgromana.Configuration");
        const sortedCats = Array.from(categories).sort();

        // IDs that are already explicitly defined in Sections 1 & 2
        // (and in CSS_BLOCK_MAP). We will NOT auto-generate rows for these.
        const explicitIds = new Set(Object.keys(CSS_BLOCK_MAP));

        // --- DRAW TABLE ---
        let html = `<table class="usgromana-table">
            <thead><tr><th>Feature / Category</th>${GROUPS.map(g => `<th class="usgromana-check-cell">${g.toUpperCase()}</th>`).join("")}</tr></thead>
            <tbody>`;

        const drawRow = (label, id, header=false) => {
            if(header) return `<tr class="usgromana-section-row"><td colspan="${GROUPS.length+1}">${label}</td></tr>`;
            let row = `<tr><td>${label}</td>`;
            GROUPS.forEach(g => {
                let val = groupsConfig[g]?.[id];
                
                // --- CRITICAL DEFAULT LOGIC ---
                // If a setting is new (undefined), should we block it?
                // Guest: Block by default. 
                // Others: Allow by default.
                if (val === undefined) {
                    val = (g !== "guest"); 
                }
                
                // Admin is always true/enabled/visible
                if (g === "admin") val = true;

                row += `<td class="usgromana-check-cell"><input type="checkbox" class="perm-chk" data-group="${g}" data-key="${id}" ${val?"checked":""} ${g==="admin"?"disabled":""}></td>`;
            });
            return row + `</tr>`;
        };

        // Section 1: Backend Security
        html += drawRow("Core API Permissions", null, true);
        html += drawRow("Access ComfyUI-Manager", "can_access_manager");
        html += drawRow("Access General API", "can_access_api");
        html += drawRow("Run Workflows (Execute)", "can_run");
        html += drawRow("Modify Workflows (Save)", "can_modify_workflows");
        html += drawRow("Upload Files", "can_upload");
        html += drawRow("SettingsExtension", "settings_extension");
        html += drawRow("See Restricted Settings", "can_see_restricted_settings");

        // Section 2: Global UI
        html += drawRow("Interface Elements", null, true);
        html += drawRow("Allow Workflow Breadcrumb", "ui_workflow_breadcrumb");
        html += drawRow("Batch Count Widget", "ui_batch_widget");
        html += drawRow("Extra Options (Batch)", "ui_extra_options");
    
        html += drawRow("Sidebar / Floating Menu", null, true);
        html += drawRow("Sidebar Menu: Save", "ui_menu_save");
        html += drawRow("Sidebar Menu: Load", "ui_menu_load");
        html += drawRow("Sidebar Menu: Queue Button", "ui_queue_button");
        html += drawRow("Sidebar: History", "ui_side_history");
        html += drawRow("Sidebar: Queue", "ui_side_queue");
        html += drawRow("Sidebar: Assets", "ui_side_assets");
        html += drawRow("Sidebar: Templates", "ui_side_templates");
        html += drawRow("Sidebar Menu: Browse Templates", "ui_menu_templates");
        html += drawRow("Sidebar Menu: Manage Extensions", "ui_menu_extensions");
        html += drawRow("Sidebar Menu: Manager Button", "ui_menu_manager");

        //  Section 3: Settings Menu Options
        html += drawRow("Settings Menu", null, true);
        html += drawRow("Settings Menu: User", "settings_user");
        html += drawRow("Settings Menu: usgromana", "settings_usgromanasettings");
        html += drawRow("Settings Menu: Mask Editor", "settings_maskeditor");
        html += drawRow("Settings Menu: Keybinding", "settings_keybinding");
        html += drawRow("Settings Menu: Appearance", "settings_makadiappearance");
        
        // Section 4: Extensions
        html += drawRow("Extension UI & Settings Categories", null, true);
        sortedCats.forEach(c => {
            const id = getSanitizedId(c);

            // If this id is already explicitly handled in Sections 1/2 (or in CSS_BLOCK_MAP),
            // skip it so we don't show duplicate/ghost toggles.
            if (explicitIds.has(id)) return;

            html += drawRow(c, id);
        });


        html += `</tbody></table>`;
        container.innerHTML = html;

        // Bind Checkboxes
        container.querySelectorAll(".perm-chk").forEach(chk => {
            chk.onchange = async () => {
                const g = chk.dataset.group;
                const k = chk.dataset.key;
                const v = chk.checked;
                
                if(!groupsConfig[g]) groupsConfig[g] = {};
                groupsConfig[g][k] = v;
                
                // Save to server
                await api.fetchApi("/usgromana/api/groups", { method: "PUT", body: JSON.stringify({ groups: { [g]: { [k]: v } } }) });
                
                // Apply immediately
                updateEnforcementStyles();
            };
        });
    }
}

// --- 4. ENFORCEMENT ENGINE (CSS INJECTION) ---

async function updateEnforcementStyles() {
    if (!currentUser) currentUser = await getData("/usgromana/api/me");
    if (!currentUser) return;

    if (!groupsConfig || Object.keys(groupsConfig).length === 0) {
        const d = await getData("/usgromana/api/groups");
        groupsConfig = d?.groups || {};
    }

    const role = currentUser.role || "user";

    // 🔧 SAFETY OVERRIDE:
    // On the *UI side*, "guest" is NEVER treated as admin,
    // even if the backend accidentally flagged it.
    if (role === "guest") {
        currentUser.is_admin = false;
    }

    const baseCfg = groupsConfig[role] || {};

    //console.log("[Usgromana] enforcement entry:", {
     //   role,
      //  is_admin: currentUser.is_admin,
       // baseCfgKeys: Object.keys(baseCfg),
        //guestCfgKeys: Object.keys(groupsConfig["guest"] || {})
    //});

    // --- BYPASS ADMIN COMPLETELY ---
    if (currentUser.is_admin) {
        const style = document.getElementById("Usgromana-css-block");
        if (style) style.textContent = "";
        return;
    }

    let css = "";

    // 🔒 HARDENED LOGIC FOR GUEST
    if (role === "guest") {
        const guestCfg = groupsConfig["guest"] || {};

        //console.log("[usgromana] enforcement (guest):", {
         //   role,
          //  guestCfgKeys: Object.keys(guestCfg)
        //});

        for (const [key, selectors] of Object.entries(CSS_BLOCK_MAP)) {
            const allowed = guestCfg[key] === true; // only explicit true is allowed
            if (!allowed) {
                css +=
                    selectors.join(", ") +
                    " { display: none !important; opacity: 0 !important; pointer-events: none !important; } \n";
            }
        }

        css += `.usgromana-blocked-item { display: none !important; }`;

        let styleTag = document.getElementById("usgromana-css-block");
        if (!styleTag) {
            styleTag = document.createElement("style");
            styleTag.id = "usgromana-css-block";
            document.head.appendChild(styleTag);
        }
        styleTag.textContent = css;

        enforceSidebar(guestCfg, role);
        enforceMenus(guestCfg, role);
        patchSaveConfirmDialog(guestCfg, role);
        return;
    }

    // ... rest of non-guest logic ...
    const cfg = baseCfg;

    console.log("[usgromana] enforcement (non-guest):", {
        role,
        cfgKeys: Object.keys(cfg),
        ui_menu_templates: cfg["ui_menu_templates"],
        ui_menu_extensions: cfg["ui_menu_extensions"]
    });

    // --- A. BLOCK GLOBAL UI ELEMENTS (Fastest) ---
    for (const [key, selectors] of Object.entries(CSS_BLOCK_MAP)) {
        let val = cfg[key];

        // ⚠️ Do NOT touch this default – it works for you:
        // undefined = allowed by default for non-guest
        if (val === undefined) {
            val = true;
        }

        if (val === false) {
            const rule =
                selectors.join(", ") +
                " { display: none !important; opacity: 0 !important; pointer-events: none !important; } \n";
            css += rule;
        }
    }

    css += `.usgromana-blocked-item { display: none !important; }`;

    // Apply to Head
    let styleTag = document.getElementById("usgromana-css-block");
    if (!styleTag) {
        styleTag = document.createElement("style");
        styleTag.id = "usgromana-css-block";
        document.head.appendChild(styleTag);
    }
    styleTag.textContent = css;

    // Trigger the JS sidebar scanner immediately
    enforceSidebar(cfg, role);
    enforceMenus(cfg, role);
    patchSaveConfirmDialog(cfg, role);
}

// Sidebar Scanner: Runs periodically to hide settings menu buttons by text content
function enforceSidebar(cfg, role) {
    const modal = document.querySelector(".comfy-modal");
    if (!modal) return;

    const items = modal.querySelectorAll(
        "button, .comfy-settings-btn, tr, .pysssss-settings-category"
    );

    items.forEach(el => {
        const txt = (el.innerText || "").trim();
        if (!txt || txt.length > 30 || txt === "Close" || txt === "Back") return;

        const catId = getSanitizedId(txt);

        let val = cfg[catId];

        // Default logic:
        //  - guest: undefined = BLOCK
        //  - others: undefined = ALLOW
        if (val === undefined) {
            val = (role !== "guest");
        }

        if (val === false) {
            el.classList.add("usgromana-blocked-item");
            el.style.display = "none"; // Inline force
        } else {
            el.classList.remove("usgromana-blocked-item");
            el.style.display = "";
        }
    });
}

// Top menu enforcement: runs on the PrimeVue menubar
function enforceMenus(cfg, role) {
    const shouldBlock = (key) => {
        let val = cfg[key];

        // Same semantics as elsewhere:
        //  - guest: undefined = BLOCK
        //  - others: undefined = ALLOW
        if (val === undefined) {
            val = (role !== "guest");
        }
        return val === false;
    };

    // Block "Browse Templates"
    if (shouldBlock("ui_menu_templates")) {
        document
            .querySelectorAll("li.p-tieredmenu-item[aria-label='Browse Templates']")
            .forEach(el => el.remove());
    }

    // Block "Manage Extensions"
    if (shouldBlock("ui_menu_extensions")) {
        document
            .querySelectorAll("li.p-tieredmenu-item[aria-label='Manage Extensions']")
            .forEach(el => el.remove());
    }

    // Block File → Save / Save As / Export / Export (API)
    if (shouldBlock("ui_menu_save")) {
        document
            .querySelectorAll(
                "li.p-tieredmenu-item[aria-label='Save'], " +
                "li.p-tieredmenu-item[aria-label='Save As'], " +
                "li.p-tieredmenu-item[aria-label='Export'], " +
                "li.p-tieredmenu-item[aria-label='Export (API)']"
            )
            .forEach(el => el.remove());
    }

    // Block File → Open
    if (shouldBlock("ui_menu_load")) {
        document
            .querySelectorAll("li.p-tieredmenu-item[aria-label='Open']")
            .forEach(el => el.remove());
    }
}

function patchSaveConfirmDialog(cfg, role) {
    // Figure out if this role is allowed to save/modify
    let canModify = true;

    if (cfg["can_modify_workflows"] === false) {
        canModify = false;
    } else if (role === "guest") {
        // Guests are blocked unless explicitly allowed
        if (cfg["can_modify_workflows"] !== true && cfg["ui_menu_save"] !== true) {
            canModify = false;
        }
    }

    if (canModify) return;

    // Look for PrimeVue confirm dialogs
    const dialogs = document.querySelectorAll(".p-confirm-dialog, .p-dialog.p-confirm-dialog");
    dialogs.forEach((dlg) => {
        if (!dlg) return;

        // Avoid double-patching the same instance
        if (dlg.dataset.usgromanaPatched === "1") return;

        const titleEl =
            dlg.querySelector(".p-dialog-header .p-dialog-title") ||
            dlg.querySelector(".p-dialog-header") ||
            dlg.querySelector(".p-confirm-dialog-message h2");

        const msgEl =
            dlg.querySelector(".p-confirm-dialog-message") ||
            dlg.querySelector(".p-dialog-content");

        const rawTitle = (titleEl && titleEl.textContent) || "";
        const rawMsg = (msgEl && msgEl.textContent) || "";
        const combined = (rawTitle + " " + rawMsg).toLowerCase();

        // Only touch dialogs that look like "unsaved changes" / "save" prompts
        if (
            !combined ||
            (!combined.includes("save") &&
             !combined.includes("unsaved") &&
             !combined.includes("changes"))
        ) {
            return;
        }

        dlg.dataset.usgromanaPatched = "1";

        // --- Rewrite title / body text ---
        if (titleEl) {
            titleEl.textContent = "Save Changes?";
        }

        if (msgEl) {
            msgEl.innerHTML = `
                <div>
                    <h3 style="margin: 0 0 0.5rem;">Access denied</h3>
                    <p style="margin: 0 0 0.5rem;">
                        Your role is not allowed to save or modify workflows.
                    </p>
                    <p style="margin: 0;">
                        You may close the workflow without saving, or cancel to keep it open.
                    </p>
                </div>
            `;
        }

        // --- Hard-block ONLY the "Save" / "accept" button ---
        let saveBtn =
            dlg.querySelector(".p-confirm-dialog-accept") ||
            dlg.querySelector("button[data-pc-section='acceptbutton']");

        if (!saveBtn) {
            // Fallback: find a button whose label includes "save"
            dlg.querySelectorAll("button").forEach((btn) => {
                const label = (btn.textContent || "").trim().toLowerCase();
                if (!saveBtn && label.includes("save")) {
                    saveBtn = btn;
                }
            });
        }

        if (saveBtn) {
            // Visual hint that it's disabled
            saveBtn.style.opacity = "0.5";

            const block = (ev) => {
                ev.preventDefault();
                ev.stopPropagation();
                ev.stopImmediatePropagation();
                console.warn("[Usgromana] Blocked Save in confirm dialog for this role");
                // Do NOT close the dialog; user can still click "Close without saving" / "Cancel"
            };

            // Catch both click and pointerdown before PrimeVue sees them
            saveBtn.addEventListener("click", block, { capture: true });
            saveBtn.addEventListener("pointerdown", block, { capture: true });
        }

        // We do NOT touch the reject / cancel button:
        // - .p-confirm-dialog-reject
        // - button[data-pc-section='rejectbutton']
        // Those remain fully usable so they can bail out safely.
    });
}

// Workflow Save / Load Interception
function isWorkflowSaveAllowed() {
    if (!currentUser || !groupsConfig) return true; // fail-open for safety until we know
    const role = currentUser.role || "user";
    const cfg = groupsConfig[role] || {};
    // If ui_menu_save is explicitly false → disallow
    if (cfg["ui_menu_save"] === false) return false;
    // Guests default to disallowed if not explicitly true
    if (role === "guest" && cfg["ui_menu_save"] !== true) return false;
    return true;
}

function isWorkflowLoadAllowed() {
    if (!currentUser || !groupsConfig) return true;
    const role = currentUser.role || "user";
    const cfg = groupsConfig[role] || {};
    if (cfg["ui_menu_load"] === false) return false;
    if (role === "guest" && cfg["ui_menu_load"] !== true) return false;
    return true;
}

// Intercept "unsaved workflow" dialogs for roles that cannot save
function guardUnsavedWorkflowDialog() {
    // If the current role IS allowed to save, do nothing
    if (isWorkflowSaveAllowed()) return;

    // PrimeVue dialogs generally use .p-dialog
    const dialogs = document.querySelectorAll(".p-dialog");
    dialogs.forEach(dialog => {
        // Skip if we already patched this dialog
        if (dialog.dataset.usgromanaGuarded === "1") return;

        const text = (dialog.innerText || "").toLowerCase();

        // Heuristic: look for dialogs that are clearly about saving workflows / unsaved changes
        if (
            !text.includes("save") || 
            (!text.includes("workflow") && !text.includes("unsaved"))
        ) {
            return;
        }

        dialog.dataset.usgromanaGuarded = "1";

        // Find the "Save" button in this dialog
        let saveButton = null;
        dialog.querySelectorAll("button").forEach(btn => {
            const label = (btn.innerText || "").trim().toLowerCase();
            if (label === "save" || label === "save workflow") {
                saveButton = btn;
            }
        });

        // If we found a Save button, kill it
        if (saveButton) {
            // You can either disable it or remove it:
            // Option A: Disable + style
            // saveButton.disabled = true;
            // saveButton.classList.add("usgromana-blocked-item");

            // Option B: Just remove it entirely (cleanest UX for guests)
            saveButton.remove();

            console.warn("[Usgromana] Blocked workflow save from unsaved-changes dialog for this role.");
        }

        // Rewrite dialog content with an Access Denied style message
        const body = dialog.querySelector(".p-dialog-content");
        if (body) {
            body.innerHTML = `
                <p><strong>Access denied</strong></p>
                <p>Your role is not allowed to save or modify workflows.</p>
                <p>You may close the workflow without saving, or cancel to keep it open.</p>
            `;
        }
    });
}

// --- WORKFLOW SAVE DENIED UI HOOKS ---

function showWorkflowDeniedToast(message) {
    // Simple top-right toast; non-intrusive but visible
    let existing = document.getElementById("usgromana-workflow-denied-toast");
    if (existing) {
        existing.remove();
    }

    const toast = document.createElement("div");
    toast.id = "usgromana-workflow-denied-toast";
    toast.style.position = "fixed";
    toast.style.top = "30px";
    toast.style.left = "50%";
    toast.style.zIndex = "10001";
    toast.style.maxWidth = "360px";
    toast.style.padding = "12px 16px";
    toast.style.borderRadius = "8px";
    toast.style.background = "rgba(40, 40, 40, 0.95)";
    toast.style.color = "#fff";
    toast.style.fontSize = "13px";
    toast.style.boxShadow = "0 8px 24px rgba(0,0,0,0.6)";
    toast.style.border = "1px solid rgba(255,255,255,0.15)";
    toast.style.display = "flex";
    toast.style.alignItems = "flex-start";
    toast.style.gap = "8px";

    toast.innerHTML = `
    <div style="font-size:16px; line-height:1;">⛔</div>
    <div style="flex:1;">
        <div style="font-weight:600; margin-bottom:2px;">Workflow action blocked</div>
        <div>${message || "You are not allowed to save or delete workflows with this account."}</div>
        </div>
        <button style="
            margin-left:8px;
            background:transparent;
            border:none;
            color:#aaa;
            cursor:pointer;
            font-size:14px;
        ">✕</button>
    `;

    const closeBtn = toast.querySelector("button");
    closeBtn.onclick = () => toast.remove();

    document.body.appendChild(toast);

    // Auto-hide after 6s
    setTimeout(() => {
        if (toast.parentNode) toast.remove();
    }, 6000);
}

function installWorkflowSaveDeniedWatcher() {
    // Avoid double-wrapping if something reloads
    if (window.fetch && window.fetch.__usgromanaWrapped) return;

    const originalFetch = window.fetch;

    async function wrappedFetch(input, init) {
        const response = await originalFetch(input, init);

        try {
            const url =
                typeof input === "string"
                    ? input
                    : (input && input.url) || "";

            // We only care about 403s on the workflow userdata endpoint
            if (response.status === 403 && url.includes("/api/userdata/workflows")) {
                console.debug(
                    "[usgromana] 403 on workflow endpoint (client-side watcher):",
                    url
                );

                let msg = "You are not allowed to perform workflow actions with this account.";

                // Try to peek at the JSON error if present
                try {
                    const clone = response.clone();
                    const data = await clone.json();
                    if (data && typeof data.error === "string") {
                        msg = data.error;
                    }
                } catch (e) {
                    // If body isn't JSON or cannot be parsed, just keep the default msg
                    console.debug("[usgromana] could not parse denied response JSON:", e);
                }

                // Extra safety: only show toast if this role is actually blocked from saving
                try {
                    if (!isWorkflowSaveAllowed()) {
                        showWorkflowDeniedToast(msg);
                    } else {
                        // If somehow a 403 slipped through for an allowed role, just log it
                        console.warn(
                            "[usgromana] Got 403 on workflow save despite isWorkflowSaveAllowed() = true. Message:",
                            msg
                        );
                    }
                } catch (e) {
                    // If helper blows up for some reason, still show the toast
                    console.warn("[usgromana] isWorkflowSaveAllowed() check failed:", e);
                    showWorkflowDeniedToast(msg);
                }
            }
        } catch (e) {
            console.warn("[usgromana] error in wrappedFetch watcher:", e);
        }

        return response;
    }

    wrappedFetch.__usgromanaWrapped = true;
    window.fetch = wrappedFetch;
}

// Intercept Ctrl+S / Ctrl+O globally for blocked roles
window.addEventListener("keydown", (ev) => {
    // Normalize
    const key = ev.key.toLowerCase();

    // Ctrl+S (save variants)
    if (ev.ctrlKey && !ev.shiftKey && key === "s") {
        if (!isWorkflowSaveAllowed()) {
            ev.preventDefault();
            ev.stopPropagation();
            console.warn("[Usgromana] Blocked Ctrl+S for this role");
            return;
        }
    }

    // Ctrl+O (open workflow)
    if (ev.ctrlKey && !ev.shiftKey && key === "o") {
        if (!isWorkflowLoadAllowed()) {
            ev.preventDefault();
            ev.stopPropagation();
            console.warn("[Usgromana] Blocked Ctrl+O for this role");
            return;
        }
    }
}, true); // use capture so we beat downstream listeners

// --- 5. INITIALIZATION ---

app.registerExtension({
    name: "usgromana.Settings",
    async setup() {
        const style = document.createElement("style");
        style.innerHTML = ADMIN_STYLES;
        document.head.appendChild(style);

        // Install backend 403 watcher for workflow save denials
        installWorkflowSaveDeniedWatcher();

        // Immediate Enforcement
        setTimeout(updateEnforcementStyles, 500);

        // Continuous Enforcement (for late loading extensions & settings modal opening)
        setInterval(() => {
            if (!currentUser || !groupsConfig) return;

            const role = currentUser.role || "user";
            const cfg = groupsConfig[role] || {};

            // Settings modal
            if (document.querySelector(".comfy-modal")) {
                enforceSidebar(cfg, role);
            }

            // Menus & save-confirm popup
            enforceMenus(cfg, role);
            patchSaveConfirmDialog(cfg, role);

            // If CSS block was nuked, rebuild it
            if (!document.getElementById("usgromana-css-block")) {
                updateEnforcementStyles();
            }
        }, 1000);

        // Register "Manage usgromana" Button in Settings
app.ui.settings.addSetting({
    id: "usgromana.Configuration",
    name: "Usgromana",
    type: () => {
        const wrapper = document.createElement("div");
        wrapper.style.display = "flex";
        wrapper.style.flexDirection = "column";
        wrapper.style.gap = "6px";

        // Logout button (above)
        const logoutBtn = document.createElement("button");
        logoutBtn.innerText = "Logout current user";
        logoutBtn.className = "usgromana-launch-btn";
        logoutBtn.style.background = "#7a2525";
        logoutBtn.style.borderColor = "#aa3a3a";
        logoutBtn.onclick = () => {
            // Hard redirect so cookies + state reset properly
            window.location.href = "/logout";
        };

        // Main management button
        const btn = document.createElement("button");
        btn.innerText = "Manage usgromana Permissions";
        btn.className = "usgromana-launch-btn";
        btn.onclick = () => new usgromanaDialog().show();

        wrapper.appendChild(logoutBtn);
        wrapper.appendChild(btn);

        // Layout helper for settings table
        setTimeout(() => {
            const td = wrapper.closest("td");
            if (td) {
                td.colSpan = 2;
                if (td.previousElementSibling) {
                    td.previousElementSibling.style.display = "none";
                }
            }
        }, 100);

        return wrapper;
    }
});
    }
});

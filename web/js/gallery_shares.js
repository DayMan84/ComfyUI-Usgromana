/**
 * Share selected Usgromana Gallery images with other accounts.
 * The gallery publishes window.USG_GALLERY_GET_SELECTED() for the current selection.
 */
const SHARE_API = "/usgromana/api/image-shares";

function selectedRelpaths() {
    if (typeof window.USG_GALLERY_GET_SELECTED !== "function") {
        return [];
    }
    return window.USG_GALLERY_GET_SELECTED().filter(Boolean);
}

function selectedOwnImages() {
    return selectedRelpaths().filter((rel) => !String(rel).startsWith("shared/"));
}

function noOwnSelectionDialog(title) {
    const selected = selectedRelpaths();
    const body = selected.length
        ? "<p>Images other accounts shared with you stay in their gallery. Select images you generated to share, review, or revoke them.</p>"
        : "<p>Select images you generated (Ctrl+click), then try again.</p>";
    openDialog({ title, body, confirmLabel: "Close", onConfirm: null });
}

async function shareRequest(path, options = {}) {
    const response = await fetch(path, {
        credentials: "include",
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        ...options,
    });
    let data = {};
    try {
        data = await response.json();
    } catch (err) {
        data = {};
    }
    if (!response.ok || data.ok === false) {
        throw new Error(data.error || `Request failed (${response.status})`);
    }
    return data;
}

function shareButtonStyle() {
    return {
        borderRadius: "999px",
        border: "1px solid rgba(148,163,184,0.45)",
        padding: "2px 10px",
        fontSize: "11px",
        cursor: "pointer",
        background: "rgba(15,23,42,0.72)",
        color: "#e5e7eb",
        marginLeft: "6px",
        display: "none",
    };
}

function ensureDialog() {
    let dialog = document.getElementById("usgromana-share-dialog");
    if (dialog) return dialog;
    dialog = document.createElement("div");
    dialog.id = "usgromana-share-dialog";
    dialog.style.cssText = [
        "position:fixed",
        "inset:0",
        "z-index:1000000",
        "display:none",
        "align-items:center",
        "justify-content:center",
        "background:rgba(0,0,0,0.45)",
    ].join(";");
    dialog.innerHTML = `
        <div style="width:min(420px,92vw);background:#0f172a;color:#e5e7eb;border:1px solid rgba(148,163,184,0.4);border-radius:12px;padding:16px;box-shadow:0 16px 40px rgba(0,0,0,0.45);">
            <div id="usgromana-share-title" style="font-weight:600;margin-bottom:8px;">Share images</div>
            <div id="usgromana-share-body" style="font-size:13px;max-height:280px;overflow:auto;"></div>
            <div id="usgromana-share-error" style="color:#fca5a5;font-size:12px;min-height:16px;margin-top:8px;"></div>
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px;">
                <button type="button" id="usgromana-share-cancel" style="padding:6px 12px;border-radius:8px;border:1px solid #475569;background:transparent;color:#e5e7eb;cursor:pointer;">Close</button>
                <button type="button" id="usgromana-share-confirm" style="padding:6px 12px;border-radius:8px;border:0;background:#0284c7;color:white;cursor:pointer;">Save</button>
            </div>
        </div>`;
    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) dialog.style.display = "none";
    });
    dialog.querySelector("#usgromana-share-cancel").onclick = () => {
        dialog.style.display = "none";
    };
    document.body.appendChild(dialog);
    return dialog;
}

function openDialog({ title, body, confirmLabel, onConfirm }) {
    const dialog = ensureDialog();
    dialog.querySelector("#usgromana-share-title").textContent = title;
    dialog.querySelector("#usgromana-share-body").innerHTML = body;
    dialog.querySelector("#usgromana-share-error").textContent = "";
    const confirm = dialog.querySelector("#usgromana-share-confirm");
    confirm.textContent = confirmLabel;
    confirm.style.display = onConfirm ? "inline-block" : "none";
    confirm.onclick = async () => {
        if (!onConfirm) {
            dialog.style.display = "none";
            return;
        }
        try {
            await onConfirm(dialog);
            dialog.style.display = "none";
        } catch (err) {
            dialog.querySelector("#usgromana-share-error").textContent = err.message || String(err);
        }
    };
    dialog.style.display = "flex";
}

async function shareSelected() {
    const relpaths = selectedOwnImages();
    if (!relpaths.length) {
        noOwnSelectionDialog("Share images");
        return;
    }
    const accounts = await shareRequest(`${SHARE_API}/accounts`);
    const users = accounts.users || [];
    if (!users.length) {
        openDialog({
            title: "Share images",
            body: "<p>There are no other accounts to share with.</p>",
            confirmLabel: "Close",
            onConfirm: null,
        });
        return;
    }
    const checks = users
        .map(
            (name) =>
                `<label style="display:block;margin:4px 0;"><input type="checkbox" value="${escapeAttr(name)}"> ${escapeText(name)}</label>`
        )
        .join("");
    openDialog({
        title: `Share ${relpaths.length} image(s)`,
        body: `<p style="margin-top:0;">These accounts will be able to see the selected images in their gallery.</p>${checks}`,
        confirmLabel: "Share",
        onConfirm: async (dialog) => {
            const usernames = [...dialog.querySelectorAll("input[type=checkbox]:checked")].map(
                (input) => input.value
            );
            if (!usernames.length) throw new Error("Choose at least one account");
            await shareRequest(SHARE_API, {
                method: "POST",
                body: JSON.stringify({ relpaths, usernames }),
            });
        },
    });
}

async function showVisibility() {
    const relpaths = selectedOwnImages();
    if (!relpaths.length) {
        noOwnSelectionDialog("Who can see these images");
        return;
    }
    const data = await shareRequest(`${SHARE_API}/visibility`, {
        method: "POST",
        body: JSON.stringify({ relpaths }),
    });
    const lines = (data.images || [])
        .map((image) => {
            const viewers = [image.owner ? `${image.owner} (owner)` : "you (owner)"]
                .concat(image.viewers || []);
            return `<div style="margin-bottom:8px;"><strong>${escapeText(image.relpath)}</strong><br>${escapeText(viewers.join(", "))}</div>`;
        })
        .join("");
    openDialog({
        title: "Who can see these images",
        body: lines || "<p>No visibility records.</p>",
        confirmLabel: "Close",
        onConfirm: null,
    });
}

async function revokeSelected() {
    const relpaths = selectedOwnImages();
    if (!relpaths.length) {
        noOwnSelectionDialog("Revoke sharing");
        return;
    }
    const data = await shareRequest(`${SHARE_API}/visibility`, {
        method: "POST",
        body: JSON.stringify({ relpaths }),
    });
    const viewers = new Set();
    (data.images || []).forEach((image) => (image.viewers || []).forEach((name) => viewers.add(name)));
    if (!viewers.size) {
        openDialog({
            title: "Revoke sharing",
            body: "<p>These images are not shared with any other account.</p>",
            confirmLabel: "Close",
            onConfirm: null,
        });
        return;
    }
    const checks = [...viewers]
        .sort()
        .map(
            (name) =>
                `<label style="display:block;margin:4px 0;"><input type="checkbox" value="${escapeAttr(name)}"> ${escapeText(name)}</label>`
        )
        .join("");
    openDialog({
        title: "Revoke sharing",
        body: `<p style="margin-top:0;">Remove visibility of the selected images from:</p>${checks}`,
        confirmLabel: "Revoke",
        onConfirm: async (dialog) => {
            const usernames = [...dialog.querySelectorAll("input[type=checkbox]:checked")].map(
                (input) => input.value
            );
            if (!usernames.length) throw new Error("Choose at least one account");
            await shareRequest(`${SHARE_API}/revoke`, {
                method: "POST",
                body: JSON.stringify({ relpaths, usernames }),
            });
        },
    });
}

function escapeText(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

function escapeAttr(value) {
    return escapeText(value).replace(/"/g, "&quot;");
}

function installShareButtons() {
    const download = [...document.querySelectorAll("button")].find((button) =>
        (button.textContent || "").startsWith("Download Selected")
    );
    if (!download || download.dataset.usgShareAttached === "1") {
        syncShareButtonVisibility(download);
        return;
    }
    download.dataset.usgShareAttached = "1";
    const parent = download.parentElement;
    if (!parent) return;

    const specs = [
        ["Share Selected", shareSelected],
        ["Who can see", showVisibility],
        ["Revoke sharing", revokeSelected],
    ];
    specs.forEach(([label, action]) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = label;
        button.dataset.usgShareAction = "1";
        Object.assign(button.style, shareButtonStyle());
        button.onclick = () => {
            action().catch((err) => {
                openDialog({
                    title: label,
                    body: `<p>${escapeText(err.message || err)}</p>`,
                    confirmLabel: "Close",
                    onConfirm: null,
                });
            });
        };
        parent.insertBefore(button, download.nextSibling);
    });
    syncShareButtonVisibility(download);
}

function syncShareButtonVisibility(download) {
    if (!download) return;
    const visible = download.style.display !== "none";
    let sibling = download.nextElementSibling;
    while (sibling) {
        if (sibling.dataset && sibling.dataset.usgShareAction === "1") {
            sibling.style.display = visible ? "inline-block" : "none";
        }
        sibling = sibling.nextElementSibling;
    }
}

setInterval(installShareButtons, 800);

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// --- Radial Menu Extension Registry API ---
/**
 * Registry for extension buttons in the Usgromana radial menu.
 * Extensions can register custom buttons that appear in the radial menu.
 */
if (!window.UsgromanaRadialMenu) {
    window.UsgromanaRadialMenu = {
        _buttons: [],
        
        /**
         * Register a new button in the radial menu.
         * @param {Object} config - Button configuration
         * @param {string} config.id - Unique button identifier (alphanumeric, lowercase, no spaces)
         * @param {string} config.label - Display name for the button
         * @param {Function} config.onClick - Function called when button is clicked
         * @param {string} [config.icon] - Optional icon/text to display (default: first letter of label)
         * @param {number} [config.order] - Optional order/position (lower numbers appear first, default: 100)
         * @returns {boolean} - True if registration was successful, false if ID already exists
         */
        register(config) {
            if (!config || !config.id || !config.label || !config.onClick) {
                console.error("[Usgromana] Radial menu button registration failed: missing required fields");
                return false;
            }
            if (!/^[a-z0-9_-]+$/.test(config.id)) {
                console.error("[Usgromana] Radial menu button registration failed: invalid ID format");
                return false;
            }
            if (this._buttons.some(b => b.id === config.id)) {
                console.warn(`[Usgromana] Radial menu button "${config.id}" already registered`);
                return false;
            }
            const button = {
                id: config.id,
                label: config.label,
                onClick: config.onClick,
                icon: config.icon || config.label.charAt(0).toUpperCase(),
                order: config.order !== undefined ? config.order : 100
            };
            this._buttons.push(button);
            this._buttons.sort((a, b) => a.order - b.order);
            console.log(`[Usgromana] Registered radial menu button: "${config.id}"`);
            if (window._usgromanaRadialMenu) {
                window._usgromanaRadialMenu.refreshButtons();
            }
            return true;
        },
        
        /**
         * Unregister a button by ID.
         * @param {string} id - Button identifier to remove
         * @returns {boolean} - True if button was found and removed
         */
        unregister(id) {
            const index = this._buttons.findIndex(b => b.id === id);
            if (index !== -1) {
                this._buttons.splice(index, 1);
                if (window._usgromanaRadialMenu) {
                    window._usgromanaRadialMenu.refreshButtons();
                }
                return true;
            }
            return false;
        },
        
        /**
         * Get all registered buttons.
         * @returns {Array} - Array of button configurations
         */
        getAll() {
            return [...this._buttons];
        },
        
        /**
         * Clear all registered buttons.
         */
        clear() {
            this._buttons = [];
        }
    };
}

// --- Floating Button Component ---
console.log("[Usgromana] floating_button.js loaded");

class UsgromanaFloatingButton {
    constructor() {
        this.button = null;
        this.radialMenu = null;
        this.isDragging = false;
        this.hasMoved = false; // Track if pointer actually moved during drag
        this.dragOffset = { x: 0, y: 0 };
        this.position = this.loadPosition();
        this.lastClickTime = 0;
        this.doubleClickDelay = 300;
        this.menuOpen = false;
        this.mouseDistanceCheckInterval = null;
        this.lastMousePosition = null;
        this.init();
    }
    
    loadPosition() {
        try {
            const saved = localStorage.getItem("usgromana_floating_button_position");
            if (saved) {
                const pos = JSON.parse(saved);
                if (pos.x >= 0 && pos.y >= 0 && pos.x <= window.innerWidth && pos.y <= window.innerHeight) {
                    return pos;
                }
            }
        } catch (e) {
            console.warn("[Usgromana] Failed to load button position:", e);
        }
        // Default: bottom-left to avoid Gallery button conflict
        return { x: 20, y: window.innerHeight - 80 };
    }
    
    savePosition() {
        try {
            localStorage.setItem("usgromana_floating_button_position", JSON.stringify(this.position));
        } catch (e) {
            console.warn("[Usgromana] Failed to save button position:", e);
        }
    }
    
    init() {
        console.log("[Usgromana] Initializing floating button...");
        console.log("[Usgromana] Document body:", !!document.body);
        console.log("[Usgromana] Window inner dimensions:", window.innerWidth, window.innerHeight);
        
        this.button = document.createElement("div");
        this.button.className = "usgromana-floating-button";
        const iconImg = document.createElement("img");
        iconImg.src = "/usgromana/assets/Dark_Usgromana.png";
        iconImg.alt = "Usgromana";
        iconImg.className = "usgromana-floating-button-icon";
        iconImg.draggable = false; // Prevent image drag
        iconImg.setAttribute("draggable", "false"); // Ensure it's not draggable
        
        iconImg.onerror = () => {
            console.error("[Usgromana] Failed to load icon, using fallback");
            iconImg.style.display = "none";
            this.button.innerHTML = '<div style="color: white; font-size: 16px; font-weight: bold;">U</div>';
        };
        iconImg.onload = () => {
            console.log("[Usgromana] Icon loaded successfully");
        };
        this.button.appendChild(iconImg);
        
        // Set explicit styles to ensure visibility and proper positioning
        Object.assign(this.button.style, {
            zIndex: "99999",
            pointerEvents: "auto",
            touchAction: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "32px",
            height: "32px",
            minWidth: "32px",
            minHeight: "32px",
            maxWidth: "32px",
            maxHeight: "32px",
            cursor: "grab",
            userSelect: "none",
            WebkitUserSelect: "none",
            opacity: "0.6", // Semi-translucent by default
            transition: "opacity 0.2s ease",
            boxSizing: "border-box",
            margin: "0",
            padding: "0"
        });
        
        // Force position fixed with setProperty to override any conflicting styles
        this.button.style.setProperty("position", "fixed", "important");
        this.button.style.setProperty("width", "32px", "important");
        this.button.style.setProperty("height", "32px", "important");
        
        // Force position fixed and size with setProperty to override any conflicting styles
        this.button.style.setProperty("position", "fixed", "important");
        this.button.style.setProperty("width", "48px", "important");
        this.button.style.setProperty("height", "48px", "important");
        
        const iconImgEl = this.button.querySelector('.usgromana-floating-button-icon');
        if (iconImgEl) {
            // Force icon size with inline styles as backup
            iconImgEl.style.setProperty("width", "32px", "important");
            iconImgEl.style.setProperty("height", "32px", "important");
            iconImgEl.style.setProperty("max-width", "32px", "important");
            iconImgEl.style.setProperty("max-height", "32px", "important");
        }
        
        this.updatePosition();
        
        // Use pointer events like Gallery button for better cross-device support
        this.button.addEventListener("pointerdown", (e) => this.handlePointerDown(e));
        // Prevent drag events on the button and image
        this.button.addEventListener("dragstart", (e) => {
            e.preventDefault();
            e.stopPropagation();
            return false;
        });
        this.button.addEventListener("drag", (e) => {
            e.preventDefault();
            e.stopPropagation();
            return false;
        });
        // Don't use native dblclick - it doesn't work well with pointer events
        // We'll detect double-click manually via click timing
        this.button.addEventListener("click", (e) => this.handleClick(e));
        this.button.addEventListener("contextmenu", (e) => {
            e.preventDefault();
            // Right-click could open menu too, but for now just prevent default
        });
        
        // Mouse enter/leave for opacity
        this.button.addEventListener("mouseenter", () => {
            if (!this.menuOpen) {
                this.button.style.opacity = "1";
            }
        });
        
        this.button.addEventListener("mouseleave", () => {
            if (!this.menuOpen) {
                this.button.style.opacity = "0.6";
            }
        });
        
        // Ensure body exists before appending
        if (!document.body) {
            console.error("[Usgromana] document.body not available!");
            return;
        }
        
        // Append to body and ensure it's at the root level, not inside any container
        // Use a high z-index to ensure it's above everything
        this.button.style.setProperty("z-index", "999999", "important");
        this.button.style.setProperty("position", "fixed", "important");
        
        // Try to append to body, or fallback to document.documentElement
        try {
            document.body.appendChild(this.button);
            console.log("[Usgromana] Button appended to document.body");
        } catch (e) {
            console.error("[Usgromana] Failed to append to body, trying documentElement:", e);
            document.documentElement.appendChild(this.button);
        }
        console.log("[Usgromana] Button added to DOM at:", this.position);
        
        this.createRadialMenu();
        
        window.addEventListener("resize", () => {
            this.constrainPosition();
            this.updatePosition();
        });
        
        // Verify button and radial menu are created
        setTimeout(() => {
            if (this.button) {
                const rect = this.button.getBoundingClientRect();
                const computed = window.getComputedStyle(this.button);
                console.log("[Usgromana] Button visibility check:", {
                    visible: rect.width > 0 && rect.height > 0,
                    width: rect.width,
                    height: rect.height,
                    left: rect.left,
                    top: rect.top,
                    zIndex: computed.zIndex,
                    display: computed.display,
                    position: computed.position,
                    opacity: computed.opacity
                });
                
                if (rect.width === 0 || rect.height === 0) {
                    console.warn("[Usgromana] Button has zero size! CSS may not be loaded.");
                }
            }
            
            // Verify radial menu
            if (this.radialMenu) {
                console.log("[Usgromana] Radial menu check:", {
                    exists: !!this.radialMenu,
                    inDOM: document.body.contains(this.radialMenu),
                    className: this.radialMenu.className,
                    children: this.radialMenu.children.length,
                    innerHTML: this.radialMenu.innerHTML.length
                });
            } else {
                console.error("[Usgromana] Radial menu is null!");
            }
        }, 200);
    }
    
    handlePointerDown(e) {
        if (e.button !== 0) return;
        
        // Prevent image drag behavior
        if (e.target.tagName === "IMG") {
            e.preventDefault();
            e.stopPropagation();
        }
        
        console.log("[Usgromana] Pointer down", e);
        console.log("[Usgromana] Button position:", this.position);
        console.log("[Usgromana] Button computed style:", window.getComputedStyle(this.button).position);
        
        // Don't prevent default immediately - let double-click work
        this.isDragging = false;
        this.hasMoved = false;
        const rect = this.button.getBoundingClientRect();
        this.dragOffset = { x: e.clientX - rect.left, y: e.clientY - rect.top };
        this.pointerStartX = e.clientX;
        this.pointerStartY = e.clientY;
        this.pointerId = e.pointerId;
        
        // Ensure button is fixed positioned
        this.button.style.setProperty("position", "fixed", "important");
        
        // Use pointer capture like Gallery button
        try {
            this.button.setPointerCapture(e.pointerId);
            console.log("[Usgromana] Pointer captured:", e.pointerId);
        } catch (err) {
            console.warn("[Usgromana] setPointerCapture failed:", err);
        }
        
        this.handlePointerMove = (e) => {
            // Only process events for this pointer
            if (e.pointerId === this.pointerId) {
                this.onPointerMove(e);
            }
        };
        this.handlePointerUp = (e) => {
            // Only process events for this pointer
            if (e.pointerId === this.pointerId) {
                this.onPointerUp(e);
            }
        };
        
        // Listen on document to catch pointer events even when pointer moves outside button
        document.addEventListener("pointermove", this.handlePointerMove);
        document.addEventListener("pointerup", this.handlePointerUp);
        document.addEventListener("pointercancel", this.handlePointerUp);
    }
    
    onPointerMove(e) {
        // Only process events for this pointer
        if (e.pointerId !== this.pointerId) return;
        
        // Only start dragging if pointer moved more than a few pixels
        const moveThreshold = 3;
        const deltaX = Math.abs(e.clientX - this.pointerStartX);
        const deltaY = Math.abs(e.clientY - this.pointerStartY);
        
        if (deltaX > moveThreshold || deltaY > moveThreshold) {
            if (!this.isDragging) {
                this.isDragging = true;
                this.hasMoved = true;
                this.button.classList.add("dragging");
                this.button.style.cursor = "grabbing";
                console.log("[Usgromana] Started dragging");
            }
        }
        
        if (!this.isDragging) return;
        
        e.preventDefault();
        e.stopPropagation();
        
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const buttonSize = 48;
        
        let newX = e.clientX - this.dragOffset.x;
        let newY = e.clientY - this.dragOffset.y;
        
        // Constrain to viewport
        newX = Math.max(8, Math.min(newX, viewportWidth - buttonSize - 8));
        newY = Math.max(8, Math.min(newY, viewportHeight - buttonSize - 8));
        
        this.position = { x: newX, y: newY };
        this.updatePosition();
        console.log("[Usgromana] Moving to:", this.position);
    }
    
    onPointerUp(e) {
        const wasDragging = this.isDragging;
        const didMove = this.hasMoved;
        
        console.log("[Usgromana] Pointer up", {
            wasDragging,
            didMove
        });
        
        // Reset dragging state
        this.isDragging = false;
        
        if (wasDragging) {
            this.button.classList.remove("dragging");
            this.button.style.cursor = "grab";
            this.savePosition();
        }
        
        try {
            this.button.releasePointerCapture(e.pointerId);
        } catch (err) {
            // Ignore
        }
        
        if (this.handlePointerMove) {
            document.removeEventListener("pointermove", this.handlePointerMove);
        }
        if (this.handlePointerUp) {
            document.removeEventListener("pointerup", this.handlePointerUp);
            document.removeEventListener("pointercancel", this.handlePointerUp);
            this.button.removeEventListener("pointerup", this.handlePointerUp);
            this.button.removeEventListener("pointercancel", this.handlePointerUp);
        }
        
        // If user didn't drag, the browser will fire a click event naturally
        // We don't need to manually dispatch - that was causing single clicks to be treated as double-clicks
        if (!didMove) {
            console.log("[Usgromana] No drag detected, browser will fire click event naturally");
        } else {
            console.log("[Usgromana] Drag detected, blocking click");
            // User dragged, reset hasMoved after delay
            setTimeout(() => {
                this.hasMoved = false;
            }, 100);
        }
    }
    
    constrainPosition() {
        const buttonSize = 48;
        this.position.x = Math.max(0, Math.min(this.position.x, window.innerWidth - buttonSize));
        this.position.y = Math.max(0, Math.min(this.position.y, window.innerHeight - buttonSize));
    }
    
    updatePosition() {
        if (this.button) {
            // Use setProperty with important to override any conflicting styles
            this.button.style.setProperty("position", "fixed", "important");
            this.button.style.setProperty("left", `${this.position.x}px`, "important");
            this.button.style.setProperty("top", `${this.position.y}px`, "important");
            this.button.style.setProperty("right", "auto", "important");
            this.button.style.setProperty("bottom", "auto", "important");
            this.button.style.setProperty("width", "48px", "important");
            this.button.style.setProperty("height", "48px", "important");
            this.button.style.setProperty("z-index", "999999", "important");
            this.button.style.setProperty("margin", "0", "important");
            this.button.style.setProperty("padding", "0", "important");
            this.button.style.setProperty("transform", "none", "important");
            
            const iconImgEl2 = this.button.querySelector('.usgromana-floating-button-icon');
            if (iconImgEl2) {
                iconImgEl2.style.setProperty("width", "32px", "important");
                iconImgEl2.style.setProperty("height", "32px", "important");
                iconImgEl2.style.setProperty("max-width", "32px", "important");
                iconImgEl2.style.setProperty("max-height", "32px", "important");
            }
            
            // Force reflow to ensure styles are applied
            void this.button.offsetHeight;
        }
        
        // If menu is open, update its position to stay anchored to the button
        if (this.menuOpen && this.radialMenu) {
            const centerX = this.position.x + 24; // Half of 48px button
            const centerY = this.position.y + 24;
            this.radialMenu.style.setProperty("left", `${centerX}px`, "important");
            this.radialMenu.style.setProperty("top", `${centerY}px`, "important");
        }
    }
    
    handleClick(e) {
        const now = Date.now();
        const timeSinceLastClick = now - this.lastClickTime;
        const isDoubleClick = timeSinceLastClick < this.doubleClickDelay && timeSinceLastClick > 0;
        
        console.log("[Usgromana] Click event fired!", {
            hasMoved: this.hasMoved,
            timeSinceLastClick: Date.now() - this.lastClickTime
        });
        
        // Only prevent click if we actually dragged significantly
        if (this.hasMoved) {
            console.log("[Usgromana] Click blocked because button was dragged");
            e.preventDefault();
            e.stopPropagation();
            this.hasMoved = false; // Reset after handling
            return;
        }
        
        // Manual double-click detection
        console.log("[Usgromana] Click timing:", {
            now,
            lastClickTime: this.lastClickTime,
            timeSinceLastClick,
            doubleClickDelay: this.doubleClickDelay,
            isDoubleClick: timeSinceLastClick < this.doubleClickDelay && timeSinceLastClick > 0
        });
        
        if (isDoubleClick) {
            // This is a double-click!
            console.log("[Usgromana] Double-click detected via click timing!");
            e.preventDefault();
            e.stopPropagation();
            this.lastClickTime = 0; // Reset to prevent triple-click
            this.handleDoubleClick(e);
            return;
        }
        
        // Single click - just update timestamp
        this.lastClickTime = now;
        console.log("[Usgromana] Single click registered, waiting for potential double-click...");
        
        // Don't do anything on single click (button is just for dragging and double-click)
    }
    
    handleDoubleClick(e) {
        const menuExists = !!this.radialMenu;
        const menuActive = this.radialMenu && this.radialMenu.classList.contains("active");
        
        console.log("[Usgromana] Double-click handler called!");
        console.log("[Usgromana] radialMenu exists:", menuExists);
        
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        // Toggle menu
        if (menuActive) {
            console.log("[Usgromana] Hiding radial menu");
            this.hideRadialMenu();
        } else {
            console.log("[Usgromana] Showing radial menu");
            if (!this.radialMenu) {
                console.warn("[Usgromana] Radial menu not created! Creating now...");
                this.createRadialMenu();
            }
            if (this.radialMenu) {
                this.showRadialMenu();
            } else {
                console.error("[Usgromana] Failed to create radial menu!");
            }
        }
    }
    
    createRadialMenu() {
        try {
            console.log("[Usgromana] Creating radial menu...");
            console.log("[Usgromana] Document body:", !!document.body);
            
            this.radialMenu = document.createElement("div");
            this.radialMenu.className = "usgromana-radial-menu";
            
            // Set initial styles to ensure it's positioned correctly
            // Menu container acts as a positioning anchor - buttons are positioned relative to its (0,0) point
            Object.assign(this.radialMenu.style, {
                position: "fixed",
                width: "0",
                height: "0",
                pointerEvents: "none",
                zIndex: "99998",
                transformOrigin: "center center"
            });
            
            if (!document.body) {
                console.error("[Usgromana] Cannot create radial menu: document.body is null!");
                return;
            }
            
            document.body.appendChild(this.radialMenu);
            console.log("[Usgromana] Radial menu element created and added to DOM");
            console.log("[Usgromana] Radial menu element:", this.radialMenu);
            console.log("[Usgromana] Radial menu parent:", this.radialMenu.parentElement);
            
            // Close menu when clicking outside
            this.outsideClickHandler = (e) => {
                if (this.radialMenu && this.radialMenu.classList.contains("active")) {
                    if (!this.radialMenu.contains(e.target) && !this.button.contains(e.target)) {
                        this.hideRadialMenu();
                    }
                }
            };
            document.addEventListener("click", this.outsideClickHandler);
            
            // Initialize buttons
            console.log("[Usgromana] Calling refreshButtons()...");
            this.refreshButtons();
            console.log("[Usgromana] Radial menu initialized successfully");
        } catch (error) {
            console.error("[Usgromana] Error creating radial menu:", error);
            console.error("[Usgromana] Error stack:", error.stack);
        }
    }
    
    refreshButtons() {
        if (!this.radialMenu) {
            console.warn("[Usgromana] Cannot refresh buttons: radial menu not created");
            return;
        }
    
        try {
            console.log("[Usgromana] Refreshing radial menu buttons...");
            const extensionButtons = (window.UsgromanaRadialMenu && typeof window.UsgromanaRadialMenu.getAll === 'function')
                ? window.UsgromanaRadialMenu.getAll()
                : [];
    
            const buttons = [
                {
                    id: "settings",
                    label: "Usgromana Settings",
                    icon: "⚙️",
                    order: 0,
                    onClick: async () => {
                        console.log("[Usgromana] Settings button clicked");
                        
                        // Function to try opening the dialog
                        const tryOpenDialog = () => {
                            // Check if dialog is already open
                            if (window._usgromanaDialogInstance && 
                                window._usgromanaDialogInstance.overlay && 
                                document.body.contains(window._usgromanaDialogInstance.overlay)) {
                                console.log("[Usgromana] Dialog is already open, focusing existing dialog");
                                // Focus the existing dialog by bringing it to front
                                window._usgromanaDialogInstance.overlay.style.zIndex = "999999";
                                return true;
                            }
                            
                            if (window.usgromanaDialog && typeof window.usgromanaDialog === 'function') {
                                console.log("[Usgromana] Opening Usgromana dialog");
                                try {
                                    // Match the exact pattern: new usgromanaDialog().show()
                                    const dialog = new window.usgromanaDialog();
                                    dialog.show().catch(err => {
                                        console.error("[Usgromana] Error in dialog.show():", err);
                                        if (app && app.ui && app.ui.dialog) {
                                            app.ui.dialog.show("Error opening Usgromana settings: " + (err.message || String(err)));
                                        }
                                    });
                                    return true;
                                } catch (err) {
                                    console.error("[Usgromana] Error creating dialog:", err);
                                    if (app && app.ui && app.ui.dialog) {
                                        app.ui.dialog.show("Error creating Usgromana settings dialog: " + (err.message || String(err)));
                                    }
                                    return false;
                                }
                            }
                            return false;
                        };
                        
                        // Try to open immediately
                        if (tryOpenDialog()) {
                            return;
                        }
                        
                        // If not available, wait a bit and try again (in case extension hasn't loaded yet)
                        console.warn("[Usgromana] window.usgromanaDialog not available, waiting and retrying...");
                        let retries = 0;
                        const maxRetries = 20;
                        
                        // Use a promise-based retry mechanism
                        return new Promise((resolve) => {
                            const retryInterval = setInterval(() => {
                                retries++;
                                console.log(`[Usgromana] Retry ${retries}/${maxRetries} to open dialog...`);
                                
                                if (tryOpenDialog()) {
                                    clearInterval(retryInterval);
                                    resolve(true);
                                    return;
                                }
                                
                                if (retries >= maxRetries) {
                                    clearInterval(retryInterval);
                                    console.error("[Usgromana] Could not open Usgromana settings - dialog not available after retries");
                                    if (app && app.ui && app.ui.dialog) {
                                        app.ui.dialog.show("Usgromana settings dialog is not available. Please ensure the Usgromana extension is loaded.");
                                    }
                                    resolve(false);
                                }
                            }, 100);
                        });
                    }
                },
                {
                    id: "logout",
                    label: "Logout",
                    icon: "🔒",
                    order: 1,
                    onClick: () => {
                        console.log("[Usgromana] Logout button clicked");
                        window.location.href = "/logout";
                    }
                },
                ...extensionButtons
            ];
    
            buttons.sort((a, b) => a.order - b.order);
    
            const centerX = this.position.x + 24; // Half of 48px button
            const centerY = this.position.y + 24;
    
            const buttonSize = 24;
            const desiredRadius = 50;
            const viewportPadding = 20;
    
            const w = window.innerWidth;
            const h = window.innerHeight;
    
            // Middle zone = full circle
            const midX1 = w * 0.33, midX2 = w * 0.67;
            const midY1 = h * 0.33, midY2 = h * 0.67;
            const inMiddle = (centerX >= midX1 && centerX <= midX2 && centerY >= midY1 && centerY <= midY2);
    
            // Quadrant detection
            const isLeft = centerX < w / 2;
            const isTop = centerY < h / 2;
    
            // Angle reference:
            // 0 = right, π/2 = down, π = left, 3π/2 = up
            let arcStart = -Math.PI / 2;
            let arcEnd = arcStart + 2 * Math.PI;
            let maxRadius;
    
            if (inMiddle) {
                // Full circle clockwise starting from top
                arcStart = -Math.PI / 2;
                arcEnd = arcStart + 2 * Math.PI;
    
                maxRadius = Math.min(
                    Math.min(centerX - viewportPadding, w - centerX - viewportPadding),
                    Math.min(centerY - viewportPadding, h - centerY - viewportPadding)
                ) - buttonSize / 2;
    
            } else if (isTop && isLeft) {
                // top-left: open right -> down
                arcStart = 0;
                arcEnd = Math.PI / 2;
    
                maxRadius = Math.min(
                    (w - centerX - viewportPadding),
                    (h - centerY - viewportPadding)
                ) - buttonSize / 2;
    
            } else if (isTop && !isLeft) {
                // top-right: open down -> left
                arcStart = Math.PI / 2;
                arcEnd = Math.PI;
    
                maxRadius = Math.min(
                    (centerX - viewportPadding),
                    (h - centerY - viewportPadding)
                ) - buttonSize / 2;
    
            } else if (!isTop && !isLeft) {
                // bottom-right: open left -> up
                arcStart = Math.PI;
                arcEnd = 3 * Math.PI / 2;
    
                maxRadius = Math.min(
                    (centerX - viewportPadding),
                    (centerY - viewportPadding)
                ) - buttonSize / 2;
    
            } else {
                // bottom-left: open up -> right
                arcStart = 3 * Math.PI / 2;
                arcEnd = 2 * Math.PI;
    
                maxRadius = Math.min(
                    (w - centerX - viewportPadding),
                    (centerY - viewportPadding)
                ) - buttonSize / 2;
            }
    
            // Clamp radius so we never go negative and stack
            const safeMaxRadius = Math.max(0, maxRadius);
            const adjustedRadius = Math.min(desiredRadius, safeMaxRadius);
    
            // Generate angles (evenly spaced)
            const count = buttons.length;
            const span = arcEnd - arcStart;
            
            const angles = (() => {
                if (count <= 0) return [];
                if (count === 1) return [arcStart + span / 2];
                // Evenly distribute buttons across the arc
                const step = span / (count - 1);
                return Array.from({ length: count }, (_, i) => arcStart + i * step);
            })();
    
            console.log("[Usgromana] Layout mode:", { inMiddle, isTop, isLeft, adjustedRadius, count });
            
            // Clear existing buttons and their tooltips
            const existingButtons = this.radialMenu.querySelectorAll(".usgromana-radial-menu-button");
            existingButtons.forEach((btn) => {
                if (btn._tooltip && btn._tooltip.parentNode) {
                    btn._tooltip.remove();
                }
            });
            this.radialMenu.innerHTML = "";
    
            // Create buttons anchored at menu origin (0,0) and animate outward using --dx/--dy
            buttons.forEach((btn, index) => {
                const angle = angles[index];
    
                let dx = Math.cos(angle) * adjustedRadius;
                let dy = Math.sin(angle) * adjustedRadius;
                
                // Constrain to viewport - check if button would go off screen
                const buttonHalfSize = buttonSize / 2;
                const finalX = centerX + dx;
                const finalY = centerY + dy;
                
                // Adjust if button would go off screen
                if (finalX - buttonHalfSize < viewportPadding) {
                    dx = viewportPadding + buttonHalfSize - centerX;
                } else if (finalX + buttonHalfSize > w - viewportPadding) {
                    dx = (w - viewportPadding - buttonHalfSize) - centerX;
                }
                
                if (finalY - buttonHalfSize < viewportPadding) {
                    dy = viewportPadding + buttonHalfSize - centerY;
                } else if (finalY + buttonHalfSize > h - viewportPadding) {
                    dy = (h - viewportPadding - buttonHalfSize) - centerY;
                }
    
                const buttonEl = document.createElement("div");
                buttonEl.className = "usgromana-radial-menu-button";
    
                // Anchor at menu origin (menu is positioned at centerX/centerY)
                Object.assign(buttonEl.style, {
                    position: "absolute",
                    left: `0px`,
                    top: `0px`,
                    width: `${buttonSize}px`,
                    height: `${buttonSize}px`,
                    borderRadius: "50%", // Ensure circular
                    // NOTE: transform/opacity handled by CSS keyframes
                    zIndex: "10001",
                    // Ensure buttons start hidden
                    opacity: "0",
                    visibility: "hidden",
                    pointerEvents: "none",
                    // Prevent text selection
                    userSelect: "none",
                    WebkitUserSelect: "none",
                    MozUserSelect: "none",
                    msUserSelect: "none",
                    WebkitTouchCallout: "none",
                    WebkitTapHighlightColor: "transparent",
                    // Ensure each button is clearly separated
                    isolation: "isolate",
                    overflow: "hidden"
                });
    
                // Target offset + stagger delay
                buttonEl.style.setProperty("--dx", `${dx}px`);
                buttonEl.style.setProperty("--dy", `${dy}px`);
                buttonEl.style.setProperty("--delay", `${index * 0.05}s`);
                
                // Debug: log CSS variables
                console.log(`[Usgromana] Button "${btn.label}" created with --dx=${dx.toFixed(1)}px, --dy=${dy.toFixed(1)}px, --delay=${(index * 0.05).toFixed(2)}s`);
    
                buttonEl.innerHTML = `
                    <div class="usgromana-radial-menu-button-icon" style="font-size: 16px; line-height: 1; display: flex; align-items: center; justify-content: center; width: 100%; height: 100%;">${btn.icon}</div>
                    <div class="usgromana-radial-menu-button-label" style="display: none;">${btn.label}</div>
                `;
                
                // Tooltip functionality - show label after 2 seconds of hover
                let hoverTimeout = null;
                let isTooltipVisible = false;
                const tooltip = document.createElement("div");
                tooltip.className = "usgromana-radial-menu-button-tooltip";
                tooltip.textContent = btn.label;
                tooltip.setAttribute("data-button-label", btn.label);
                // Initially hidden
                tooltip.style.display = "none";
                tooltip.style.opacity = "0";
                tooltip.style.visibility = "hidden";
                document.body.appendChild(tooltip);
                
                const showTooltip = () => {
                    if (isTooltipVisible) {
                        console.log(`[Usgromana] Tooltip already visible for "${btn.label}"`);
                        return;
                    }
                    
                    console.log(`[Usgromana] Attempting to show tooltip for "${btn.label}"`);
                    
                    // Get button position
                    const rect = buttonEl.getBoundingClientRect();
                    const buttonRight = rect.right;
                    const buttonCenterY = rect.top + rect.height / 2;
                    const tooltipSpacing = 12; // Space between button and tooltip
                    
                    console.log(`[Usgromana] Button rect:`, rect);
                    console.log(`[Usgromana] Tooltip element:`, tooltip);
                    
                    // Position tooltip to the right of the button, vertically centered
                    tooltip.style.setProperty("left", `${buttonRight + tooltipSpacing}px`, "important");
                    tooltip.style.setProperty("top", `${buttonCenterY}px`, "important");
                    tooltip.style.setProperty("z-index", "999999", "important");
                    tooltip.style.setProperty("position", "fixed", "important");
                    tooltip.style.setProperty("display", "block", "important");
                    tooltip.style.setProperty("visibility", "visible", "important");
                    
                    // Ensure tooltip is in the DOM
                    if (!tooltip.parentNode) {
                        document.body.appendChild(tooltip);
                        console.log(`[Usgromana] Appended tooltip to body`);
                    }
                    
                    // Force reflow
                    void tooltip.offsetHeight;
                    void tooltip.getBoundingClientRect();
                    
                    // Show with animation
                    setTimeout(() => {
                        tooltip.classList.add("show");
                        tooltip.style.setProperty("opacity", "1", "important");
                        isTooltipVisible = true;
                        console.log(`[Usgromana] Tooltip shown for "${btn.label}" at (${buttonRight + tooltipSpacing}, ${buttonCenterY})`);
                        console.log(`[Usgromana] Tooltip computed style:`, window.getComputedStyle(tooltip));
                    }, 10);
                };
                
                const hideTooltip = () => {
                    if (!isTooltipVisible) return;
                    
                    tooltip.classList.remove("show");
                    tooltip.style.opacity = "0";
                    
                    // Hide after transition
                    setTimeout(() => {
                        tooltip.style.display = "none";
                        tooltip.style.visibility = "hidden";
                        isTooltipVisible = false;
                    }, 200);
                };
                
                buttonEl.addEventListener("mouseenter", (e) => {
                    console.log(`[Usgromana] Mouse entered button "${btn.label}"`, e);
                    // Ensure button can receive hover events
                    buttonEl.style.setProperty("pointer-events", "auto", "important");
                    // Add hover class for visual feedback
                    buttonEl.classList.add("hover-active");
                    // Start timer to show tooltip after 2 seconds
                    hoverTimeout = setTimeout(() => {
                        console.log(`[Usgromana] Showing tooltip for "${btn.label}" after 2 seconds`);
                        showTooltip();
                    }, 2000);
                });
                
                buttonEl.addEventListener("mouseleave", () => {
                    console.log(`[Usgromana] Mouse left button "${btn.label}"`);
                    // Remove hover class
                    buttonEl.classList.remove("hover-active");
                    // Clear timer if mouse leaves before 2 seconds
                    if (hoverTimeout) {
                        clearTimeout(hoverTimeout);
                        hoverTimeout = null;
                    }
                    // Hide tooltip if visible
                    hideTooltip();
                });
                
                // Store tooltip reference for cleanup
                buttonEl._tooltip = tooltip;
    
                // Prevent text selection
                buttonEl.addEventListener("selectstart", (e) => {
                    e.preventDefault();
                    return false;
                });
                buttonEl.addEventListener("dragstart", (e) => {
                    e.preventDefault();
                    return false;
                });
                buttonEl.addEventListener("mousedown", (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                });
                buttonEl.addEventListener("click", async (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    e.stopImmediatePropagation();
                    console.log(`[Usgromana] Radial menu button "${btn.label}" clicked`);
                    
                    // Call onClick handler (may be async)
                    try {
                        if (btn.onClick && typeof btn.onClick === 'function') {
                            const result = btn.onClick();
                            // If onClick returns a promise, await it
                            if (result && typeof result.then === 'function') {
                                await result.catch(err => {
                                    console.error(`[Usgromana] Error in async onClick handler for "${btn.label}":`, err);
                                });
                            }
                        } else {
                            console.warn(`[Usgromana] Button "${btn.label}" has no onClick handler`);
                        }
                    } catch (error) {
                        console.error(`[Usgromana] Error in onClick handler for "${btn.label}":`, error);
                    }
                    
                    // Hide menu after a short delay to allow the click to process
                    setTimeout(() => {
                        this.hideRadialMenu();
                    }, 100);
                    
                    return false;
                });
    
                this.radialMenu.appendChild(buttonEl);
            });
    
            // Position menu at the floating button center
            this.radialMenu.style.setProperty("left", `${centerX}px`, "important");
            this.radialMenu.style.setProperty("top", `${centerY}px`, "important");
            this.radialMenu.style.setProperty("position", "fixed", "important");
            this.radialMenu.style.setProperty("transform-origin", "center center", "important");
    
            console.log(`[Usgromana] Created ${buttons.length} radial menu buttons`);
        } catch (error) {
            console.error("[Usgromana] Error refreshing buttons:", error);
            console.error("[Usgromana] Error stack:", error.stack);
        }
    }
            
    showRadialMenu() {
        if (!this.radialMenu) {
            console.warn("[Usgromana] Radial menu not created yet!");
            return;
        }
    
        console.log("[Usgromana] Showing radial menu...");
        console.log("[Usgromana] Button position:", this.position);
    
        this.menuOpen = true;
        if (this.button) this.button.style.opacity = "1";
    
        // Always rebuild buttons for current position (this sets --dx/--dy/--delay per button)
        this.refreshButtons();
    
        // Anchor radial menu at button center
        const centerX = this.position.x + 16; // Half of 32px button
        const centerY = this.position.y + 16;
    
        this.radialMenu.style.setProperty("left", `${centerX}px`, "important");
        this.radialMenu.style.setProperty("top", `${centerY}px`, "important");
        this.radialMenu.style.setProperty("position", "fixed", "important");
        this.radialMenu.style.setProperty("pointer-events", "auto", "important");
        this.radialMenu.style.setProperty("visibility", "visible", "important");
    
        // Put menu above the button so you can see it
        // (floating button is z-index 10000; menu must be higher)
        this.radialMenu.style.setProperty("z-index", "10001", "important");
    
        this.radialMenu.classList.add("active");
    
        // Query buttons AFTER refreshButtons() populated the DOM
        let buttons = this.radialMenu.querySelectorAll(".usgromana-radial-menu-button");
        console.log(`[Usgromana] Found ${buttons.length} radial menu buttons`);
    
        if (buttons.length === 0) {
            console.warn("[Usgromana] No buttons found in radial menu! Recreating...");
            this.refreshButtons();
    
            const buttonsAfterRefresh = this.radialMenu.querySelectorAll(".usgromana-radial-menu-button");
            console.log(`[Usgromana] After refresh: ${buttonsAfterRefresh.length} buttons`);
            if (buttonsAfterRefresh.length === 0) {
                console.error("[Usgromana] Failed to create buttons!");
                return;
            }
            // Update buttons reference to the newly created ones
            buttons = buttonsAfterRefresh;
        }

        buttons.forEach((btn) => {
            // Remove inline overrides that might conflict with animations
            // BUT keep display: flex as it's needed for layout
            btn.style.removeProperty("opacity");
            btn.style.removeProperty("transform");
            btn.style.removeProperty("visibility");
            // Don't remove display - it's needed!
            // Don't remove pointer-events here - we'll set it properly during animation
            btn.style.removeProperty("z-index");
            // animation-delay is set via CSS variable, but remove inline if any
            btn.style.removeProperty("animation-delay");
        });
          
        // IMPORTANT:
        // - Do NOT force opacity/visibility/transform on each button here
        // - Let CSS keyframes control that via animate-in/out
        // - Use a 2-frame kick + layout flush so animation reliably fires in ComfyUI
        requestAnimationFrame(() => {
            void this.radialMenu.offsetHeight; // flush
    
            requestAnimationFrame(() => {
                const btns = this.radialMenu.querySelectorAll(".usgromana-radial-menu-button");
                console.log(`[Usgromana] Found ${btns.length} buttons to animate`);
                
                btns.forEach((btn, index) => {
                    // Remove any existing animation classes
                    btn.classList.remove("animate-out");
                    btn.classList.remove("animate-in");
                    
                    // Force a reflow to ensure the class removal is processed
                    void btn.offsetHeight;
                    
                    // Get CSS variables for final position
                    const dx = btn.style.getPropertyValue("--dx") || "0px";
                    const dy = btn.style.getPropertyValue("--dy") || "0px";
                    const delayMs = parseFloat(btn.style.getPropertyValue("--delay") || "0") * 1000;
                    
                    console.log(`[Usgromana] Button ${index}: dx=${dx}, dy=${dy}, delay=${delayMs}ms`);
                    
                    // Ensure display is set (needed for visibility)
                    btn.style.display = "flex";
                    
                    // Clear any existing inline styles that might interfere
                    btn.style.removeProperty("opacity");
                    btn.style.removeProperty("transform");
                    btn.style.removeProperty("pointer-events");
                    
                    // Set initial state (hidden at center) - this matches CSS default
                    btn.style.opacity = "0";
                    btn.style.visibility = "hidden";
                    btn.style.pointerEvents = "none";
                    btn.style.transform = "translate(-50%, -50%) translate(0px, 0px) scale(0)";
                    
                    // Add the animation class (CSS will handle transition-delay via --delay variable)
                    btn.classList.add("animate-in");
                    
                    // Force a reflow to ensure initial state is applied
                    void btn.offsetHeight;
                    
                    // Set final state - CSS transition will animate from initial to final
                    // Use requestAnimationFrame to ensure the initial state is painted first
                    requestAnimationFrame(() => {
                        setTimeout(() => {
                            btn.style.setProperty("visibility", "visible", "important");
                            btn.style.setProperty("opacity", "1", "important");
                            btn.style.setProperty("pointer-events", "auto", "important");
                            // Set transform with scale(1) for hover animation to work
                            // The scale(1) allows hover to scale to 1.15 and active to scale to 0.9
                            btn.style.setProperty("transform", `translate(-50%, -50%) translate(${dx}, ${dy}) scale(1)`, "important");
                            // Ensure background is visible
                            btn.style.setProperty("background", "rgba(30, 30, 30, 0.98)", "important");
                            btn.style.setProperty("border", "3px solid rgba(255, 255, 255, 0.3)", "important");
                            btn.style.setProperty("display", "flex", "important");
                            console.log(`[Usgromana] Button ${index} ("${btn.querySelector('.usgromana-radial-menu-button-label')?.textContent || 'unknown'}") animated to: ${dx}, ${dy}`);
                        }, 10);
                    });
                });

                // Start tracking mouse distance AFTER the menu is animating
                this.startMouseDistanceTracking();

                console.log("[Usgromana] Radial menu shown with", btns.length, "buttons");
                
                // Fallback: ensure buttons are visible after transition should complete
                setTimeout(() => {
                    btns.forEach((btn, idx) => {
                        const computed = window.getComputedStyle(btn);
                        if (computed.opacity === "0" || computed.opacity === "0px") {
                            console.warn(`[Usgromana] Button ${idx} still invisible after transition, forcing visibility`);
                            const dx = btn.style.getPropertyValue("--dx") || "0px";
                            const dy = btn.style.getPropertyValue("--dy") || "0px";
                            btn.style.setProperty("opacity", "1", "important");
                            btn.style.setProperty("transform", `translate(-50%, -50%) translate(${dx}, ${dy}) scale(1)`, "important");
                            btn.style.setProperty("background", "rgba(30, 30, 30, 0.98)", "important");
                            btn.style.setProperty("border", "3px solid rgba(255, 255, 255, 0.3)", "important");
                            btn.style.setProperty("visibility", "visible", "important");
                        }
                    });
                }, 500); // After all transitions should complete (320ms + delays + buffer)
            });
        });
    
        // Optional: debug visibility after animation starts
        setTimeout(() => {
            const btns = this.radialMenu.querySelectorAll(".usgromana-radial-menu-button");
            const visibleButtons = Array.from(btns).filter(btn => {
                const rect = btn.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            });
    
            console.log("[Usgromana] Menu visibility check:", {
                totalButtons: btns.length,
                visibleButtons: visibleButtons.length,
                menuActive: this.radialMenu.classList.contains("active")
            });
        }, 180);
    }    
    
    hideRadialMenu() {
        if (!this.radialMenu) return;
    
        this.menuOpen = false;
        if (this.button) this.button.style.opacity = "0.6";
    
        this.stopMouseDistanceTracking();
    
        const buttons = Array.from(this.radialMenu.querySelectorAll(".usgromana-radial-menu-button"));
        
        // Clean up tooltips
        buttons.forEach((btn) => {
            if (btn._tooltip && btn._tooltip.parentNode) {
                // Hide tooltip immediately
                btn._tooltip.classList.remove("show");
                btn._tooltip.style.display = "none";
                btn._tooltip.style.visibility = "hidden";
                btn._tooltip.style.opacity = "0";
            }
        });
        
        // Animate out - get current position and animate back to center
        buttons.forEach((btn) => {
            const dx = btn.style.getPropertyValue("--dx") || "0px";
            const dy = btn.style.getPropertyValue("--dy") || "0px";
            const delayMs = parseFloat(btn.style.getPropertyValue("--delay") || "0") * 1000;
            
            // Set transition for closing
            btn.style.transition = "transform 0.22s cubic-bezier(.2,.9,.2,1), opacity 0.22s cubic-bezier(.2,.9,.2,1)";
            btn.style.transitionDelay = `${delayMs}ms`;
            
            btn.classList.remove("animate-in");
            btn.classList.add("animate-out");
            
            // Force reflow
            void btn.offsetHeight;
            
            // Animate back to center
            setTimeout(() => {
                btn.style.opacity = "0";
                btn.style.transform = "translate(-50%, -50%) translate(0px, 0px) scale(0)";
                // Hide visibility after transition completes
                setTimeout(() => {
                    btn.style.visibility = "hidden";
                }, 220); // After transition duration
            }, 10);
        });
    
        // After animation, remove active + remove any inline overrides
        const CLOSE_MS = 260;
        setTimeout(() => {
            if (!this.radialMenu) return;
    
            this.radialMenu.classList.remove("active");
            this.radialMenu.style.setProperty("pointer-events", "none", "important");
    
            // IMPORTANT: remove inline poison so next open can animate
            buttons.forEach((btn) => {
                btn.classList.remove("animate-out");
                btn.classList.remove("animate-in");
                btn.style.removeProperty("transform");
                btn.style.removeProperty("opacity");
                btn.style.removeProperty("visibility");
                btn.style.removeProperty("display");
                btn.style.removeProperty("pointer-events");
                btn.style.removeProperty("z-index");
                btn.style.removeProperty("animation-delay");
                // Ensure buttons are hidden when menu is closed
                btn.style.setProperty("visibility", "hidden", "important");
                btn.style.setProperty("opacity", "0", "important");
                
                // Clean up tooltips
                if (btn._tooltip && btn._tooltip.parentNode) {
                    btn._tooltip.remove();
                    btn._tooltip = null;
                }
            });
        }, CLOSE_MS);
    }
        
    startMouseDistanceTracking() {
        this.stopMouseDistanceTracking(); // Clear any existing interval
        
        const checkDistance = () => {
            if (!this.menuOpen || !this.radialMenu) {
                this.stopMouseDistanceTracking();
                return;
            }
            
            // Get current mouse position (we'll track it via mousemove)
            if (!this.lastMousePosition) return;
            
            const mx = this.lastMousePosition.x;
            const my = this.lastMousePosition.y;
            
            // Calculate distance from button center
            const buttonCenterX = this.position.x + 16; // Half of 32px button
            const buttonCenterY = this.position.y + 16;
            const distanceFromButton = Math.sqrt(
                Math.pow(mx - buttonCenterX, 2) + Math.pow(my - buttonCenterY, 2)
            );
            
            // Check distance from any menu button
            const buttons = this.radialMenu.querySelectorAll(".usgromana-radial-menu-button");
            let minDistanceToButton = Infinity;
            
            buttons.forEach(btn => {
                const rect = btn.getBoundingClientRect();
                const btnCenterX = rect.left + rect.width / 2;
                const btnCenterY = rect.top + rect.height / 2;
                const distance = Math.sqrt(
                    Math.pow(mx - btnCenterX, 2) + Math.pow(my - btnCenterY, 2)
                );
                minDistanceToButton = Math.min(minDistanceToButton, distance);
            });
            
            // If mouse is 100px away from button AND 100px away from all menu buttons, close menu
            if (distanceFromButton > 100 && minDistanceToButton > 100) {
                console.log("[Usgromana] Mouse moved away, closing menu");
                this.hideRadialMenu();
            }
        };
        
        // Track mouse position
        this.mouseMoveHandler = (e) => {
            this.lastMousePosition = { x: e.clientX, y: e.clientY };
        };
        document.addEventListener("mousemove", this.mouseMoveHandler);
        
        // Check distance periodically
        this.mouseDistanceCheckInterval = setInterval(checkDistance, 50);
    }
    
    stopMouseDistanceTracking() {
        if (this.mouseDistanceCheckInterval) {
            clearInterval(this.mouseDistanceCheckInterval);
            this.mouseDistanceCheckInterval = null;
        }
        if (this.mouseMoveHandler) {
            document.removeEventListener("mousemove", this.mouseMoveHandler);
            this.mouseMoveHandler = null;
        }
        this.lastMousePosition = null;
    }
}

// --- Extension Detection for Radial Menu ---
function detectExtensionsForRadialMenu() {
    if (window.location.pathname.includes("gallery") || 
        document.querySelector('[href*="gallery"]') ||
        window.UsgromanaGallery) {
        if (!window.UsgromanaRadialMenu._buttons.some(b => b.id === "gallery")) {
            window.UsgromanaRadialMenu.register({
                id: "gallery",
                label: "Gallery",
                icon: "🖼️",
                order: 10,
                onClick: () => {
                    if (window.UsgromanaGallery && typeof window.UsgromanaGallery.open === "function") {
                        window.UsgromanaGallery.open();
                    } else if (window.location.pathname !== "/usgromana-gallery") {
                        window.location.href = "/usgromana-gallery";
                    }
                }
            });
        }
    }
    // Note: Extensions should explicitly register themselves using window.UsgromanaRadialMenu.register()
    // Auto-detection removed to prevent non-functional buttons from appearing
}

// --- Initialize Floating Button ---
console.log("[Usgromana] Registering FloatingButton extension...");

if (typeof app !== 'undefined' && app.registerExtension) {
    app.registerExtension({
        name: "Usgromana.FloatingButton",
        async setup() {
            console.log("[Usgromana] FloatingButton extension setup() called");
            // Wait a bit for other extensions to load
            setTimeout(() => {
                console.log("[Usgromana] Creating floating button...");
                // Detect extensions
                detectExtensionsForRadialMenu();
                
                // Create floating button
                if (!window._usgromanaFloatingButton) {
                    try {
                        window._usgromanaFloatingButton = new UsgromanaFloatingButton();
                        window._usgromanaRadialMenu = window._usgromanaFloatingButton;
                        console.log("[Usgromana] Floating button created successfully");
                    } catch (error) {
                        console.error("[Usgromana] Error creating floating button:", error);
                    }
                } else {
                    console.log("[Usgromana] Floating button already exists");
                }
                
                // Set up observer to hide/show button when dialog opens/closes
                // Check periodically if dialog is open and hide button accordingly
                setInterval(() => {
                    if (window._usgromanaFloatingButton && window._usgromanaFloatingButton.button) {
                        const dialogOpen = window._usgromanaDialogInstance && 
                                          window._usgromanaDialogInstance.overlay && 
                                          document.body.contains(window._usgromanaDialogInstance.overlay);
                        
                        if (dialogOpen) {
                            // Hide button when dialog is open
                            if (window._usgromanaFloatingButton.button.style.display !== "none") {
                                window._usgromanaFloatingButton.button.style.display = "none";
                            }
                        } else {
                            // Show button when dialog is closed (unless menu is open)
                            if (!window._usgromanaFloatingButton.menuOpen && 
                                window._usgromanaFloatingButton.button.style.display === "none") {
                                window._usgromanaFloatingButton.button.style.display = "flex";
                            }
                        }
                    }
                }, 100);
            }, 1000);
        }
    });
    console.log("[Usgromana] FloatingButton extension registered");
} else {
    console.error("[Usgromana] app.registerExtension not available! app:", typeof app);
}


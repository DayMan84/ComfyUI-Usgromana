import { $el } from "/scripts/ui.js";

async function setupLogout() {
  try {
    await new Promise((resolve) => {
      const interval = setInterval(() => {
        const sideBar = document.querySelector(".side-tool-bar-end");
        if (sideBar) {
          clearInterval(interval);
          resolve();
        }
      }, 100);
    });

    function logoutAction() {
      try {
        localStorage.clear();
        sessionStorage.clear();
        document.cookie.split(";").forEach((cookie) => {
          const cookieName = cookie.split("=")[0].trim();
          document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/`;
        });

        window.location.href = "/logout";
      } catch (error) {
        console.error("Error during logout process:", error);
      }
    }

    const sideBarEnd = document.querySelector(".side-tool-bar-end");
    const comfyMenu = document.querySelector(".comfy-menu");
    
    if (sideBarEnd) {
      try {
        $el(
          "button",
          {
            className:
              "p-button p-component p-button-icon-only p-button-text comfy-settings-btn side-bar-button p-button-secondary usgromana-logout",
            type: "button",
            id: "logout-button",
            ariaLabel: "Logout",
            dataset: {
              pcName: "button",
              pDisabled: false,
              pcSection: "root",
              pdTooltip: false,
              "v-6ab4daa6": "",
              "v-33cac83a": "",
            },
            parent: sideBarEnd,
            onclick: logoutAction,
          },
          [
            $el("li", {
              className: "pi pi-sign-out side-bar-button-icon",
              dataset: {
                "v-6ab4daa6": "",
              },
            }),
          ]
        );
      } catch (err) {
        console.error("Error creating sidebar logout button:", err);
      }
    }

    if (comfyMenu) {
      try {
        $el(
          "button",
          {
            textContent: "Logout",
            id: "logout-menu-button",
            parent: comfyMenu,
            onclick: logoutAction,
          },
          [
            $el("li", {
              className: "pi pi-sign-out logout-icon",
            }),
          ]
        );
      } catch (err) {
        console.error("Error creating menu logout button:", err);
      }
    }

  } catch (error) {
    console.error("Error setting up Logout button:", error);
  }
}

let isSettingUp = false;
let logoutIntervalId = null;
let logoutButtonExists = false;

// Function to check and setup logout button
async function checkAndSetupLogout() {
  // Early exit if button already exists and is connected
  if (logoutButtonExists) {
    const btn = document.getElementById("logout-button");
    if (btn && btn.isConnected) {
      return; // Button exists and is valid
    }
    logoutButtonExists = false; // Button was removed, reset flag
  }
  
  const logoutBtn = document.getElementById("logout-button");
  if (logoutBtn === null && !isSettingUp) {
    isSettingUp = true;
    await setupLogout();
    isSettingUp = false;
    
    // Check if button was successfully created
    const newBtn = document.getElementById("logout-button");
    if (newBtn) {
      logoutButtonExists = true;
      // Once button exists, we can stop the interval
      if (logoutIntervalId) {
        clearInterval(logoutIntervalId);
        logoutIntervalId = null;
      }
    }
  }
}

// Register as ComfyUI extension to ensure it loads
if (typeof app !== 'undefined' && app.registerExtension) {
  app.registerExtension({
    name: "Usgromana.Logout",
    async setup() {
      // Start the interval to check for logout button
      // Only run if interval isn't already running (prevent duplicates)
      if (!logoutIntervalId) {
        logoutIntervalId = setInterval(checkAndSetupLogout, 500);
        // Store for potential cleanup
        window._usgromanaLogoutInterval = logoutIntervalId;
      }
    }
  });
} else {
  // Fallback if app.registerExtension is not available
  // Only run if interval isn't already running
  if (!logoutIntervalId) {
    logoutIntervalId = setInterval(checkAndSetupLogout, 500);
    window._usgromanaLogoutInterval = logoutIntervalId;
  }
}
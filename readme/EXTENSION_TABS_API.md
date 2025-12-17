# Usgromana Admin Panel Extension Tabs API

This API allows ComfyUI extensions to add custom tabs to the Usgromana admin panel, enabling them to manage permissions and settings within the unified admin interface.

## Overview

Extensions can register custom tabs that appear alongside the built-in tabs (Users & Roles, Permissions & UI, IP Rules, User Env, NSFW Management). Each extension tab gets its own container and can render any content it needs.

## API Reference

### `window.UsgromanaAdminTabs.register(config)`

Registers a new tab in the admin panel.

**Parameters:**
- `config` (Object) - Tab configuration object
  - `id` (string, required) - Unique tab identifier. Must be lowercase alphanumeric with underscores/hyphens only (e.g., `"myextension"`, `"custom-perms"`)
  - `label` (string, required) - Display name for the tab (e.g., `"My Extension"`)
  - `render` (Function, required) - Async function that renders the tab content
    - Parameters:
      - `container` (HTMLElement) - The container element to render into
      - `context` (Object) - Context object with available data:
        - `usersList` (Array) - List of all users
        - `groupsConfig` (Object) - Groups configuration object
        - `currentUser` (Object) - Current logged-in user object
  - `order` (number, optional) - Tab order/position (lower numbers appear first, default: 100)
  - `icon` (string, optional) - Reserved for future use

**Returns:** `boolean` - `true` if registration was successful, `false` if ID already exists or validation failed

**Example:**
```javascript
window.UsgromanaAdminTabs.register({
    id: "myextension",
    label: "My Extension",
    order: 50,
    render: async (container, context) => {
        const { usersList, groupsConfig, currentUser } = context;
        
        container.innerHTML = `
            <div style="padding: 20px;">
                <h3>My Extension Settings</h3>
                <p>Manage permissions for My Extension here.</p>
                <div id="myextension-content"></div>
            </div>
        `;
        
        // Render your custom content
        const contentDiv = container.querySelector("#myextension-content");
        // ... your rendering logic
    }
});
```

### `window.UsgromanaAdminTabs.unregister(id)`

Unregisters a tab by ID.

**Parameters:**
- `id` (string) - Tab identifier to remove

**Returns:** `boolean` - `true` if tab was found and removed

**Example:**
```javascript
window.UsgromanaAdminTabs.unregister("myextension");
```

### `window.UsgromanaAdminTabs.getAll()`

Gets all registered extension tabs.

**Returns:** `Array` - Array of tab configurations

### `window.UsgromanaAdminTabs.clear()`

Clears all registered extension tabs.

## Usage Examples

### Basic Tab Registration

```javascript
// In your extension's JavaScript file
app.registerExtension({
    name: "MyExtension.Admin",
    async setup() {
        // Register tab when extension loads
        window.UsgromanaAdminTabs.register({
            id: "myextension",
            label: "My Extension",
            order: 50,
            render: async (container, context) => {
                container.innerHTML = `
                    <div style="padding: 20px;">
                        <h3>My Extension Permissions</h3>
                        <p>Configure access controls for My Extension.</p>
                    </div>
                `;
            }
        });
    }
});
```

### Advanced Tab with Permissions Management

```javascript
window.UsgromanaAdminTabs.register({
    id: "gallery-perms",
    label: "Gallery Permissions",
    order: 60,
    render: async (container, context) => {
        const { usersList, groupsConfig } = context;
        
        // Fetch your extension's permission data
        const perms = await fetch("/myextension/api/permissions")
            .then(r => r.json())
            .catch(() => ({}));
        
        container.innerHTML = `
            <div style="padding: 20px;">
                <h3>Gallery Access Control</h3>
                <table class="usgromana-table">
                    <thead>
                        <tr>
                            <th>User</th>
                            <th>Can View Gallery</th>
                            <th>Can Upload</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="gallery-perms-body">
                    </tbody>
                </table>
            </div>
        `;
        
        // Populate table
        const tbody = container.querySelector("#gallery-perms-body");
        usersList.forEach(user => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td>${user.username}</td>
                <td><input type="checkbox" data-user="${user.username}" data-perm="view"></td>
                <td><input type="checkbox" data-user="${user.username}" data-perm="upload"></td>
                <td><button class="usgromana-btn">Save</button></td>
            `;
            tbody.appendChild(row);
        });
        
        // Add event handlers
        container.querySelectorAll("button").forEach(btn => {
            btn.onclick = async () => {
                // Save permissions logic
                const row = btn.closest("tr");
                const username = row.querySelector("input").dataset.user;
                // ... save logic
            };
        });
    }
});
```

### Tab with Dynamic Content Updates

```javascript
window.UsgromanaAdminTabs.register({
    id: "extension-stats",
    label: "Extension Stats",
    order: 70,
    render: async (container, context) => {
        container.innerHTML = `
            <div style="padding: 20px;">
                <h3>Extension Statistics</h3>
                <div id="stats-content">Loading...</div>
                <button class="usgromana-btn" id="refresh-stats">Refresh</button>
            </div>
        `;
        
        const updateStats = async () => {
            const statsDiv = container.querySelector("#stats-content");
            statsDiv.textContent = "Loading...";
            
            try {
                const stats = await fetch("/myextension/api/stats")
                    .then(r => r.json());
                
                statsDiv.innerHTML = `
                    <p>Active Users: ${stats.activeUsers}</p>
                    <p>Total Requests: ${stats.totalRequests}</p>
                `;
            } catch (error) {
                statsDiv.textContent = "Error loading stats";
            }
        };
        
        await updateStats();
        
        container.querySelector("#refresh-stats").onclick = updateStats;
    }
});
```

## Best Practices

1. **Register Early**: Register your tab in your extension's `setup()` method to ensure it's available when the admin panel opens.

2. **Use Unique IDs**: Choose a unique tab ID that won't conflict with other extensions. Use your extension name as a prefix (e.g., `"myextension-perms"`).

3. **Handle Errors**: Wrap your render function in try-catch or handle errors gracefully to prevent breaking the admin panel.

4. **Use Existing Styles**: Leverage the existing CSS classes (`.usgromana-table`, `.usgromana-btn`, etc.) for consistent styling.

5. **Async Operations**: The render function is async, so you can fetch data from your backend before rendering.

6. **Context Data**: Use the provided context object to access user lists and group configurations rather than making redundant API calls.

7. **Ordering**: Use appropriate order values to position your tab logically:
   - 0-9: Built-in tabs
   - 10-49: Reserved for future built-in tabs
   - 50-99: Recommended for extension tabs
   - 100+: Default for extension tabs

## Integration with Permissions System

Extensions can integrate with Usgromana's permission system by:

1. **Reading Groups Config**: Use `context.groupsConfig` to read existing permission configurations
2. **Custom Permission Keys**: Add your own permission keys to the groups config (e.g., `"myextension_view"`, `"myextension_upload"`)
3. **Backend API**: Create backend endpoints to manage your extension's permissions
4. **UI Enforcement**: Use the same CSS blocking system or create custom enforcement logic

## Notes

- Tabs are registered globally and persist for the page lifetime
- The admin panel must be opened by an admin user
- Extension tabs appear after built-in tabs by default (unless order is set lower)
- Tab IDs must be unique; duplicate registrations are ignored with a warning
- The render function is called each time the tab is shown (not cached)


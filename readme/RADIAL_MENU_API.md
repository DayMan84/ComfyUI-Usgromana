# Usgromana Radial Menu API

This API allows ComfyUI extensions to add custom buttons to the Usgromana floating button's radial menu, enabling quick access to extension features.

## Overview

The Usgromana floating button appears as a draggable button on the screen. When double-clicked, it opens a radial menu with buttons for Settings, Logout, and any registered extension buttons.

## API Reference

### `window.UsgromanaRadialMenu.register(config)`

Registers a new button in the radial menu.

**Parameters:**
- `config` (Object) - Button configuration object
  - `id` (string, required) - Unique button identifier. Must be lowercase alphanumeric with underscores/hyphens only (e.g., `"gallery"`, `"my-extension"`)
  - `label` (string, required) - Display name for the button (e.g., `"Gallery"`)
  - `onClick` (Function, required) - Function called when button is clicked
  - `icon` (string, optional) - **Custom icon to display** (default: first letter of label). Can be:
    - **Emoji** (recommended): `"🖼️"`, `"⚙️"`, `"🔒"`, `"🎨"`, `"📊"`, etc.
    - **Unicode symbols**: `"★"`, `"◆"`, `"●"`, `"→"`, etc.
    - **Single character text**: `"A"`, `"1"`, `"+"`, `"?"`, etc.
    - **HTML entities**: `"&star;"`, `"&hearts;"`, etc.
  - `order` (number, optional) - Button order/position (lower numbers appear first, default: 100)

**Returns:** `boolean` - `true` if registration was successful, `false` if ID already exists or validation failed

**Example:**
```javascript
window.UsgromanaRadialMenu.register({
    id: "gallery",
    label: "Gallery",
    icon: "🖼️",
    order: 10,
    onClick: () => {
        // Open gallery
        window.location.href = "/usgromana-gallery";
    }
});
```

### `window.UsgromanaRadialMenu.unregister(id)`

Unregisters a button by ID.

**Parameters:**
- `id` (string) - Button identifier to remove

**Returns:** `boolean` - `true` if button was found and removed

**Example:**
```javascript
window.UsgromanaRadialMenu.unregister("gallery");
```

### `window.UsgromanaRadialMenu.getAll()`

Gets all registered buttons.

**Returns:** `Array` - Array of button configurations

### `window.UsgromanaRadialMenu.clear()`

Clears all registered buttons.

## Usage Examples

### Basic Button Registration with Custom Icon

```javascript
// In your extension's JavaScript file
app.registerExtension({
    name: "MyExtension.RadialMenu",
    async setup() {
        // Register button when extension loads
        window.UsgromanaRadialMenu.register({
            id: "myextension",
            label: "My Extension",
            icon: "🔧",  // Custom emoji icon
            order: 20,
            onClick: () => {
                // Open your extension's UI
                console.log("Opening My Extension");
                // Your code here
            }
        });
    }
});
```

### Custom Icon Examples

Extensions can use any icon they want. Here are various icon options:

```javascript
// Emoji icons (most common and visually appealing)
window.UsgromanaRadialMenu.register({
    id: "gallery",
    label: "Gallery",
    icon: "🖼️",  // Picture frame emoji
    onClick: () => { /* ... */ }
});

window.UsgromanaRadialMenu.register({
    id: "analytics",
    label: "Analytics",
    icon: "📊",  // Chart emoji
    onClick: () => { /* ... */ }
});

window.UsgromanaRadialMenu.register({
    id: "art-generator",
    label: "Art Generator",
    icon: "🎨",  // Artist palette emoji
    onClick: () => { /* ... */ }
});

// Unicode symbols
window.UsgromanaRadialMenu.register({
    id: "favorites",
    label: "Favorites",
    icon: "★",  // Star symbol
    onClick: () => { /* ... */ }
});

window.UsgromanaRadialMenu.register({
    id: "settings-advanced",
    label: "Advanced Settings",
    icon: "◆",  // Diamond symbol
    onClick: () => { /* ... */ }
});

// Single character text
window.UsgromanaRadialMenu.register({
    id: "help",
    label: "Help",
    icon: "?",  // Question mark
    onClick: () => { /* ... */ }
});

window.UsgromanaRadialMenu.register({
    id: "add",
    label: "Add Item",
    icon: "+",  // Plus sign
    onClick: () => { /* ... */ }
});
```

### Advanced Button with Custom Logic

```javascript
window.UsgromanaRadialMenu.register({
    id: "gallery-viewer",
    label: "Gallery",
    icon: "🖼️",
    order: 10,
    onClick: () => {
        // Check if gallery is already open
        if (window.location.pathname === "/usgromana-gallery") {
            // Refresh gallery
            window.location.reload();
        } else {
            // Navigate to gallery
            window.location.href = "/usgromana-gallery";
        }
    }
});
```

### Button with Async Operations

```javascript
window.UsgromanaRadialMenu.register({
    id: "async-action",
    label: "Sync Data",
    icon: "🔄",
    order: 30,
    onClick: async () => {
        try {
            const response = await fetch("/myextension/api/sync");
            const data = await response.json();
            console.log("Sync completed:", data);
        } catch (error) {
            console.error("Sync failed:", error);
        }
    }
});
```

## Built-in Buttons

The radial menu includes two built-in buttons that cannot be unregistered:

1. **Settings** (order: 0) - Opens the Usgromana admin panel
2. **Logout** (order: 1) - Logs out the current user

Extension buttons appear after these built-in buttons, sorted by their `order` value.

## Best Practices

1. **Register Early**: Register your button in your extension's `setup()` method to ensure it's available when the floating button is created.

2. **Use Unique IDs**: Choose a unique button ID that won't conflict with other extensions. Use your extension name as a prefix (e.g., `"myextension-action"`).

3. **Custom Icons**: You can specify any icon you want using the `icon` parameter:
   - **Emoji** (recommended): Most visually appealing and widely supported. Examples: `"🖼️"`, `"⚙️"`, `"🔒"`, `"🎨"`, `"📊"`, `"🔍"`, `"💾"`, `"🚀"`
   - **Unicode symbols**: `"★"`, `"◆"`, `"●"`, `"→"`, `"←"`, `"↑"`, `"↓"`
   - **Single characters**: `"A"`, `"1"`, `"+"`, `"-"`, `"?"`, `"!"`
   - If no icon is provided, the first letter of the label is used automatically
   - Icons are displayed at 16px font size in the center of the circular button
   - **Tip**: Choose icons that are recognizable at small sizes and clearly represent your extension's function

4. **Order Values**: Use appropriate order values to position your button logically:
   - 0-1: Reserved for built-in buttons (Settings, Logout)
   - 2-9: Recommended for core/useful extensions
   - 10-49: Recommended for common extensions
   - 50-99: Default for extension buttons
   - 100+: Less common or optional extensions

5. **Handle Errors**: Wrap your onClick function in try-catch if it performs async operations to prevent breaking the menu.

6. **Check Availability**: Before using the API, check if it's available:
   ```javascript
   if (window.UsgromanaRadialMenu) {
       window.UsgromanaRadialMenu.register({...});
   }
   ```

## Integration with Floating Button

The floating button:
- Can be dragged anywhere on the screen (click and hold to move)
- Opens the radial menu on double-click
- Saves its position in localStorage
- Automatically detects some extensions (like Usgromana-Gallery)

## Notes

- Buttons are registered globally and persist for the page lifetime
- The floating button must be loaded before extensions can register buttons
- Button IDs must be unique; duplicate registrations are ignored with a warning
- The onClick function is called when the button is clicked, and the menu automatically closes
- The radial menu animates buttons in and out for a smooth user experience



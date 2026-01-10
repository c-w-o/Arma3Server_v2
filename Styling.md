# ui-kit/0 — Styling & CSS Contract

This document defines the **styling contract** of **ui-kit/0**.

It explains which CSS variables (design tokens) exist, how components consume them,
and what integrators are allowed to override. This contract is **stable by design**
and intended to prevent accidental visual breakage.

---

## 1. Core Principles

ui-kit/0 styling follows these rules:

1. **Components never hard-code colors, spacing, or typography**
2. All visual decisions are expressed through **CSS custom properties**
3. Integrators may override tokens, not component internals
4. JavaScript must not depend on computed styles
5. Missing CSS triggers a minimal fallback stylesheet

---

## 2. CSS Loading Contract

ui-kit/0 expects the following stylesheet to be loaded:

```html
<link rel="stylesheet" href="ui-kit-0.theme.css">
<link rel="stylesheet" href="ui-kit-0.css">
```

The presence of CSS is detected via:

```css
:root {
  --ui-css-loaded: 1;
}
```

If this marker is missing, `ui-kit-0.js` injects a minimal fallback stylesheet.

---

## 3. Design Token Philosophy

All tokens are:

- **Semantic**, not component-specific
- **Themeable** (light / dark / auto)
- **Density-aware** (comfortable / compact)

Components only *read* tokens — they never define them.

---

## 4. Global Design Tokens

Defined in `ui-kit-0.theme.css`.

### Typography

```css
--ui-font-family
--ui-font-size
--ui-line-height
```

### Radius

```css
--ui-radius-sm
--ui-radius-md
--ui-radius-lg
```

### Spacing Scale

```css
--ui-space-1
--ui-space-2
--ui-space-3
--ui-space-4
--ui-space-5
```

Derived layout tokens:

```css
--ui-gap
--ui-padding
```

---

## 5. Control Metrics

Used by all inputs, buttons, and selects.

```css
--ui-control-height
--ui-control-padding-x
--ui-control-padding-y
```

These values must remain compatible with pointer input.

---

## 6. Semantic Colors

### Base Colors

```css
--ui-color-bg
--ui-color-surface
--ui-color-surface-muted
--ui-color-border
```

### Text

```css
--ui-color-text
--ui-color-text-muted
```

### Accent & Status

```css
--ui-color-accent
--ui-color-accent-hover

--ui-color-danger
--ui-color-danger-bg

--ui-color-ok
--ui-color-ok-bg
```

Components never reference raw color values directly.

---

## 7. Focus & Motion

```css
--ui-focus-ring
--ui-shadow-sm
--ui-duration-fast
--ui-ease
```

Focus styles must remain visible in all themes.

---

## 8. Theme Switching

Theme selection is controlled via a root attribute:

```html
<html data-ui-theme="light">
<html data-ui-theme="dark">
<html data-ui-theme="auto">
```

Dark theme overrides are defined in `ui-kit-0.theme.css` and must only override tokens,
never component selectors.

---

## 9. Density Switching

Density is controlled via:

```html
<html data-ui-density="comfortable">
<html data-ui-density="compact">
```

Compact mode reduces:
- spacing
- control height
- font size

No layout breakage is allowed between densities.

---

## 10. Component Styling Rules

### Allowed

✔ Override CSS variables  
✔ Add custom classes around components  
✔ Scope overrides to containers  

### Forbidden

✘ Modifying internal DOM structure  
✘ Relying on undocumented class names  
✘ Using `!important` on core tokens  
✘ Styling via JavaScript

---

## 11. Scoped Third-Party Styling

Third-party components are styled **only within explicit scopes**.

Example:

```css
.json-editor {
  /* scoped overrides only */
}
```

No global overrides of third-party styles are permitted.

---

## 12. Fallback CSS

If main CSS is missing, ui-kit/0 injects a fallback stylesheet providing:

- readable layout
- functional controls
- minimal visual hierarchy

Fallback CSS is **not themeable** and is intended only as a safety net.

---

## 13. Integrator Example

```css
/* Custom brand accent */
:root {
  --ui-color-accent: #7c3aed;
  --ui-color-accent-hover: #6d28d9;
}

/* Compact admin view */
html[data-ui-density="compact"] {
  --ui-font-size: 12px;
}
```

---

## 14. Stability Guarantee

The following are considered **public API** and will not change without a major version:

- Token names
- Theme and density attributes
- CSS presence detection marker
- Component-token relationships

---

End of styling contract.
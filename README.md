# ui-kit/0

ui-kit/0 is a small, explicit UI toolkit for browser-based applications.
It is intended as a stable foundation for tools, dashboards, and configuration-oriented user interfaces.

The project favors **clarity, predictability, and explicit structure** over abstraction depth or framework-level convenience.

---

## Background and Motivation

Many modern frontend solutions optimize primarily for rapid iteration and developer ergonomics.
This often results in:
- complex build pipelines
- implicit dependency resolution
- tight coupling between tooling and runtime behavior
- large abstraction layers that are difficult to audit or debug later

ui-kit/0 takes a more conservative approach.

It assumes environments where:
- dependencies must be explicit and inspectable
- offline or restricted-network operation is common
- applications are expected to remain understandable and maintainable over long periods

---

## Design Philosophy

### Explicitness First

ui-kit/0 avoids implicit behavior by design.

- No automatic dependency loading
- No hidden globals
- No side effects during module import
- No runtime code generation

If a component depends on a third-party library, that dependency must be:
- loaded explicitly
- visible at runtime
- documented

Missing dependencies do not crash the application.  
Affected features disable themselves in a controlled and visible way.

---

### Browser as the Runtime

The browser is treated as the actual runtime environment, not merely as a compilation target.

ui-kit/0 relies on:
- native ES modules
- standard DOM APIs
- plain JavaScript classes
- CSS custom properties for styling

There is no virtual DOM and no framework-specific rendering model.
DOM updates are explicit and local.

---

### Deterministic Behavior

The framework favors:
- simple control flow
- explicit state updates
- predictable rendering behavior

Components are designed to be understandable with standard browser developer tools.
Understanding runtime behavior should not require knowledge of hidden framework internals.

---

### Offline and Long-Term Use

ui-kit/0 assumes that applications may run:
- without internet access
- with vendored third-party libraries
- in controlled or security-sensitive environments

No runtime dependency on CDNs or package registries is required.

---

## Project Goals

ui-kit/0 is **not** intended to be:
- a full design system
- a replacement for large SPA frameworks
- a component marketplace
- a visual layout or page builder

It **is** intended to:
- provide a small and reliable UI foundation
- support configuration-heavy and data-driven interfaces
- integrate cleanly into existing applications
- remain understandable without framework-specific knowledge

---

## Non-Goals and Anti-Patterns

ui-kit/0 deliberately avoids certain patterns and use cases.
Using it against these constraints will usually result in unnecessary complexity or frustration.

---

### Not a Full Application Framework

ui-kit/0 is not intended to manage:
- routing
- data fetching
- authentication
- application bootstrapping
- deployment concerns

It provides UI building blocks, not an application runtime.

---

### Not a Virtual DOM or Reactive Rendering System

ui-kit/0 does not:
- diff virtual trees
- batch renders automatically
- infer dependencies between state and UI

DOM updates are explicit and local.
Components update because code tells them to, not because a reactive engine decided to.

---

### Not Optimized for Large-Scale SPA Patterns

ui-kit/0 is not designed for:
- thousands of dynamically mounted components
- deep component hierarchies driven by data
- highly dynamic view switching at large scale

It is better suited for:
- tool-like interfaces
- dashboards
- configuration and control panels

---

### No Implicit Two-Way Binding

There is no automatic synchronization between UI and state.

If a component updates state:
- it does so explicitly
- at a clearly defined point in the code

If state updates UI:
- it happens via explicit subscriptions

Patterns that rely on hidden two-way data binding are intentionally avoided.

---

### No Build-Time Magic

ui-kit/0 does not assume:
- a bundler
- a transpiler
- tree-shaking
- code generation

While build tooling can be added externally, the toolkit itself does not depend on it.

---

### Not a Styling Framework

ui-kit/0 does not aim to:
- enforce a visual identity
- provide a comprehensive theme catalog
- replace CSS frameworks

Styling is token-based and minimal by design.
Visual consistency is the responsibility of the integrator.

---

### Avoid Using ui-kit/0 If You Need

ui-kit/0 is likely a poor fit if you need:
- heavy animation systems
- design-system-level theming
- highly dynamic, content-driven UIs
- rapid prototyping with minimal structure

In those cases, a more opinionated framework may be more appropriate.

---

### Anti-Pattern: Hiding Dependencies

Do not:
- implicitly load third-party libraries
- rely on globals without documenting them
- mask missing dependencies

The system is designed to make dependencies visible and explicit.

---

### Anti-Pattern: Treating Components as Declarative Templates

ui-kit/0 components are stateful objects with lifecycle.

They are not intended to be:
- stateless render functions
- declarative templates
- purely data-driven view descriptions

Attempting to use them as such will work against the design.

---

## Architectural Overview

The project is structured into clearly separated layers, each with a specific responsibility.

---

### Core Layer (No External Dependencies)

The core layer is fully standalone and safe to use in any environment.

It provides:
- a minimal base component abstraction with lifecycle and cleanup handling
- layout primitives (rows, columns, cards, spacers)
- basic controls (buttons, text fields, checkboxes)
- structural components (tabs, selection groups, tables)
- a small, immutable, path-based state store

Key characteristics:
- zero third-party dependencies
- explicit DOM manipulation
- deterministic ownership and cleanup
- predictable rendering behavior

The core layer does not depend on any optional features.

---

### Optional Feature Layer

More advanced functionality is implemented as optional modules.

Examples include:
- JSON Schema validation
- schema-driven configuration editors
- expert JSON editing
- chart rendering

These features rely on explicitly loaded third-party libraries
(e.g. AJV, json-editor, Ace, Chart.js).

If a dependency is missing:
- the affected feature reports its unavailability
- a fallback UI is used where reasonable
- the rest of the system continues to function

---

### Styling Layer

Styling is separated from logic and driven by CSS custom properties.

- Design tokens define colors, spacing, typography, and layout values
- Components consume tokens but do not hard-code design decisions
- Themes are applied by overriding tokens, not by modifying component logic

A minimal fallback stylesheet exists to keep components usable if the main CSS is missing.

---

## State and Data Flow

ui-kit/0 follows a simple and explicit data flow model:

- application state lives in a central Store
- updates are immutable
- components may subscribe to the full state or to specific paths
- state changes trigger explicit UI updates

There is no implicit two-way binding and no hidden synchronization layer.

---

## Dependency Strategy

Dependencies are handled explicitly and conservatively:

- Core: no dependencies
- Optional features: documented global dependencies
- No dynamic imports
- No automatic polyfills
- No runtime dependency resolution

This makes deployments reproducible and easy to audit.

---

## Documentation Layout

Documentation is intentionally split into separate concerns:

1. **Project Overview (this document)**  
   Philosophy, goals, and architecture

2. **API Documentation**  
   Detailed reference for components, classes, and usage patterns

3. **Styling and Theming Guide**  
   Design tokens, themes, and customization rules

Each document focuses on a single aspect and avoids mixing conceptual and reference material.

---

## License

ui-kit/0 is released under the MIT License.  
Third-party libraries retain their respective licenses.

See the included SBOM for exact versions and license details.
# ui-kit/0 — API Documentation

ui-kit/0 is a minimalist UI framework for modern browsers, built on native ES modules,
explicit dependencies, and predictable DOM behavior. It is designed to work without
any mandatory build tooling and to degrade gracefully when optional dependencies
are not present.

---

## 1. Usage Model

ui-kit/0 is consumed directly in the browser.

- Core modules have **no third-party dependencies**
- Optional features rely on **explicit global objects**
- All components render **real DOM elements**
- Cleanup is deterministic via explicit destroy logic

---

## 2. Installation

### CSS

```html
<link rel="stylesheet" href="./src/ui-kit-0.theme.css" />
<link rel="stylesheet" href="./src/ui-kit-0.css" />
```

If the CSS is missing, ui-kit/0 automatically injects a minimal fallback stylesheet.

### JavaScript

```html
<script type="module" src="./src/ui-kit-0.js"></script>
```

---

## 3. Optional Third-Party Dependencies

Load only what you need.

| Feature | Global | Files |
|------|------|------|
| JSON Schema validation | window.ajv7 | ajv7.bundle.min.js |
| Visual JSON editor | window.JSONEditor | jsoneditor.min.js |
| Expert JSON editor | window.ace | ace.js, mode-json.js, worker-json.js |
| Charts | window.Chart | chart.umd.min.js |

All third-party libraries must be loaded **before** ui-kit-0.js.

---

## 4. BaseElement

All UI components extend BaseElement.

### Core API

```js
new BaseElement(tag)
  .appendTo(parent)
  .setText(text)
  .setStyle(styles)
  .addClass(className)
  .on(event, handler)
  .own(cleanupFn)
  .add(child)
  .destroy()
```

### Example

```js
const el = new UI.BaseElement("div")
  .setText("Hello")
  .appendTo(document.body);
```

---

## 5. Layout Components

### Div / HDiv / VDiv

```js
new UI.HDiv({ gap: 8 })
  .add(new UI.Button("OK"))
  .add(new UI.Button("Cancel"));
```

### Card

```js
new UI.Card({ title: "Settings" })
  .add(new UI.TextField("Alice"));
```

---

## 6. Controls

### Button

```js
new UI.Button("Save", { variant: "primary" })
  .onClick(() => alert("Saved"));
```

Variants: primary, secondary, danger

### TextField (Store-bound)

```js
new UI.TextField()
  .bind(store, "user.name");
```

### Checkbox

```js
new UI.Checkbox(true, { label: "Enabled", slider: true });
```

### Select

```js
new UI.Select({
  options: ["dev", "prod"],
  value: "dev"
});
```

---

## 7. Store

A small clone-on-write state container.

```js
const store = new UI.Store({ count: 0 });

store.subscribePath("count", v => console.log(v));
store.setPath("count", 1);
```

---

## 8. SelectionGroup

```js
const sel = new UI.SelectionGroup()
  .addItem("a", "Alpha")
  .addItem("b", "Beta")
  .onChange(id => console.log(id));
```

Keyboard-accessible and ARIA-aware.

---

## 9. Tabs

```js
const tabs = new UI.Tabs();
tabs.addTab("one", "One", () => new UI.Text("Hello"));
tabs.addTab("two", "Two", () => new UI.Text("World"));
```

Automatically switches to a dropdown on overflow.

---

## 10. TableView

```js
new UI.TableView({
  columns: [
    { key: "name", label: "Name" },
    { key: "age", label: "Age" }
  ],
  data: [{ name: "Alice", age: 31 }]
});
```

---

## 11. ImageView

Supports raster images and inline SVG.

```js
new UI.ImageView({
  src: "/logo.svg",
  width: 64,
  height: 64,
  inlineSvg: true
});
```

Inline SVG must be trusted input.

---

## 12. Validation

```js
const validate = UI.makeValidator(schema);
const result = validate(data);
```

If AJV is missing, validation succeeds with a warning.

---

## 13. Charts

### ChartView

```js
const chart = new UI.ChartView({
  type: "line",
  map: state => ({
    labels: state.x,
    datasets: [{ label: "Y", data: state.y }]
  })
});

chart.bind(store);
```

### LineChartCard

```js
const lc = new UI.LineChartCard({
  title: "Metrics",
  maxPoints: 600
});

lc.push(Date.now(), 42);
```

---

## 14. SchemaConfigEditor

High-level JSON configuration editor.

```js
new UI.SchemaConfigEditor({
  store,
  schema,
  valuePath: "config"
});
```

- User tab: json-editor
- Expert tab: Ace or textarea fallback
- Store updates only when data is valid

---

## 15. Minimal Full index.html

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>ui-kit/0 Demo</title>

  <link rel="stylesheet" href="./src/ui-kit-0.theme.css" />
  <link rel="stylesheet" href="./src/ui-kit-0.css" />

  <script src="./src/third_party/ajv/ajv7.bundle.min.js"></script>
  <script src="./src/third_party/ace/ace.js"></script>
  <script src="./src/third_party/ace/mode-json.js"></script>
  <script src="./src/third_party/ace/worker-json.js"></script>
  <script src="./src/third_party/json-editor/jsoneditor.min.js"></script>
  <script src="./src/third_party/chartjs/chart.umd.min.js"></script>
</head>

<body>
  <div id="app"></div>

  <script type="module">
    import * as UI from "./src/ui-kit-0.js";

    const app = new UI.VDiv({ gap: 12 })
      .appendTo(document.getElementById("app"));

    const store = new UI.Store({ count: 0 });

    new UI.Button("Click")
      .appendTo(app)
      .onClick(() => store.setPath("count", store.getPath("count") + 1));

    const txt = new UI.Text("Count: 0").appendTo(app);
    store.subscribePath("count", v => txt.setText(`Count: ${v}`));
  </script>
</body>
</html>
```

---

End of document.
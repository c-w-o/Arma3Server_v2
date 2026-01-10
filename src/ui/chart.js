// src/ui/chart.js
import { BaseElement } from "./base.js";
import { Card } from "./layout.js";

/**
 * ChartView wraps Chart.js (UMD global: window.Chart).
 *
 * Design goals:
 * - No rebuild by default: always update().
 * - Store binding via mapper: map(state) -> Chart.js { labels, datasets }.
 * - Lazy init: works with Card.add(chart) (no need to call appendTo()).
 * - Offline: requires local third_party/chart.umd(.min).js script include.
 */
export class ChartView extends BaseElement {
  constructor({
    type = "line",
    map = null,          // function(state) => { labels, datasets }
    data = null,         // optional initial Chart.js data
    options = null,      // optional Chart.js options
    height = 260,        // CSS height in px (Chart.js needs canvas height)
  } = {}) {
    super("canvas");
    this.el.classList.add("ui-chart");

    this.type = type;
    this.map = map;
    this.data = data ?? { labels: [], datasets: [] };
    this.options = options ?? {};
    this.height = height;

    this.chart = null;

    // Make sizing predictable for responsive charts
    this.el.style.width = "100%";
    this.el.style.height = `${height}px`;
    this.el.style.display = "block";
  }

  _ensureChart() {
    if (this.chart) return true;

    // Must be in DOM, otherwise Chart.js gets wrong sizes in many browsers.
    if (!this.el.isConnected) return false;

    const Chart = window.Chart;
    if (!Chart) {
      console.error(
        "Chart.js not found. Make sure you included ./src/third_party/chart.umd(.min).js before the module script."
      );
      return false;
    }

    const ctx = this.el.getContext("2d");
    if (!ctx) return false;

    // Reasonable defaults; user can override via options
    const mergedOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        tooltip: { enabled: true },
        legend: { display: true },
      },
      ...this.options,
    };

    this.chart = new Chart(ctx, {
      type: this.type,
      data: this.data,
      options: mergedOptions,
    });

    return true;
  }

  /**
   * Update chart data (no rebuild). If chart isn't ready yet, it will
   * initialize on the next animation frame when connected.
   */
  setData(nextData) {
    this.data = nextData ?? { labels: [], datasets: [] };

    if (this._ensureChart()) {
      this.chart.data = this.data;
      this.chart.update();
    } else {
      requestAnimationFrame(() => {
        if (this._ensureChart()) {
          this.chart.data = this.data;
          this.chart.update();
        }
      });
    }
    return this;
  }

  /**
   * Bind to store. Mapper maps state -> Chart.js data shape.
   * Uses update() only (no rebuild).
   */
  bind(store, mapFn = null) {
    const mapper = mapFn ?? this.map;
    if (typeof mapper !== "function") {
      throw new Error("ChartView.bind(store, mapFn): mapFn must be a function(state) => {labels, datasets}");
    }

    const update = () => {
      const state = store.get();
      const next = mapper(state);
      this.setData(next);
    };

    update();
    this.own(store.subscribe(() => update()));
    return this;
  }

  destroy() {
    try { this.chart?.destroy(); } catch { /* ignore */ }
    this.chart = null;
    super.destroy({ remove: true });
  }
}

/**
 * ChartCard: always render charts inside a Card.
 * Title is required by design.
 */
export class ChartCard extends Card {
  constructor({
    title,
    chart = {}, // passed to ChartView
  } = {}) {
    if (!title) throw new Error("ChartCard requires a title.");
    super({ title });

    this.chartView = new ChartView(chart);
    this.add(this.chartView);
  }

  bind(store, mapFn) {
    this.chartView.bind(store, mapFn);
    return this;
  }

  setData(data) {
    this.chartView.setData(data);
    return this;
  }

  destroy() {
    this.chartView?.destroy();
    super.destroy({ remove: true });
  }
}

// ------------------------------------------------------------
// Typed charts (one class per chart type)
// ------------------------------------------------------------

function _capArray(arr, max) {
  if (!Array.isArray(arr) || max == null) return;
  while (arr.length > max) arr.shift();
}

function _capChartData(data, maxPoints) {
  if (!data || maxPoints == null) return data;

  _capArray(data.labels, maxPoints);
  if (Array.isArray(data.datasets)) {
    for (const ds of data.datasets) _capArray(ds?.data, maxPoints);
  }
  return data;
}

/**
 * LineChartCard
 * - Multi-line supported (multiple datasets).
 * - No points (pure line).
 * - Fixed window: maxPoints (default: 600).
 * - Push API: push(label, values)
 *
 * Note: "values" can be:
 * - number (for single dataset)
 * - array of numbers (for multi dataset by index)
 * - object {datasetId: value, ...} if you prefer keyed datasets (optional)
 */
export class LineChartCard extends ChartCard {
  constructor({
    title,
    height = 260,
    maxPoints = 600,
    datasets = [{ label: "Series", data: [] }],
    options = {},
    // How to render timestamps on the X axis (category axis).
    // If you later switch to a real time-scale (with adapter), you can change this.
    labelFromTs = (tsMs) => {
      const d = new Date(tsMs);
      const hh = String(d.getHours()).padStart(2, "0");
      const mm = String(d.getMinutes()).padStart(2, "0");
      const ss = String(d.getSeconds()).padStart(2, "0");
      return `${hh}:${mm}:${ss}`;
    },
  } = {}) {
    const lineOptions = {
      animation: false,
      normalized: true,
      elements: {
        point: { radius: 0, hitRadius: 6 }, // no visible points
        line: { tension: 0 },
      },
      plugins: {
        tooltip: { enabled: true },
        legend: { display: true },
      },
      scales: {
        // category axis (string labels) -> no adapter required
        x: { ticks: { maxRotation: 0 } },
      },
      ...options,
    };
    
    super({
      title,
      chart: {
        type: "line",
        height,
        data: { labels: [], datasets: datasets.map(d => ({ ...d, data: d.data ?? [] })) },
        options: lineOptions,
      }
    });

    this.maxPoints = maxPoints;
    this.labelFromTs = labelFromTs;
    this._sampleIndex = 0;
    
    if (!window.Chart) {
      this.add(new Text("Chart.js not loaded", { muted: true }));
      return;
    }
  }

  setData(data) {
    super.setData(_capChartData(data, this.maxPoints));
    return this;
  }

  /**
   * Push one sample.
   * - tsMs optional. If missing -> use incrementing index label.
   * - values can be number | number[] | { [seriesLabel]: number }
   */
  pushSample({ tsMs = null, values } = {}) {
    const d = this.chartView.data ?? { labels: [], datasets: [] };
    d.labels ??= [];
    d.datasets ??= [];

    const label = (tsMs != null)
      ? this.labelFromTs(tsMs)
      : String(++this._sampleIndex);

    d.labels.push(label);

    if (typeof values === "number") {
      if (!d.datasets[0]) d.datasets[0] = { label: "Series", data: [] };
      (d.datasets[0].data ??= []).push(values);
    } else if (Array.isArray(values)) {
      for (let i = 0; i < values.length; i++) {
        if (!d.datasets[i]) d.datasets[i] = { label: `Series ${i + 1}`, data: [] };
        (d.datasets[i].data ??= []).push(values[i]);
      }
    } else if (values && typeof values === "object") {
      for (const [key, val] of Object.entries(values)) {
        let ds = d.datasets.find(x => x.label === key);
        if (!ds) {
          ds = { label: key, data: [] };
          d.datasets.push(ds);
        }
        (ds.data ??= []).push(val);
      }
    }

    this.setData(d); // caps + update()
    return this;
  }

  // Convenience for “no timestamp” polling
  pushValues(values) {
    return this.pushSample({ tsMs: null, values });
  }

  /**
   * Replace data from a batch (e.g. backend bundle).
   * samples: [{ tsMs?: number, values: ... }, ...]
   */
  setSamples(samples = []) {
    const d = { labels: [], datasets: [] };

    for (const s of samples) {
      // reuse push logic into a temporary structure
      this.chartView.data = d;
      this.pushSample(s);
    }

    // restore & render (pushSample already caps+updates, but we do a final setData for safety)
    this.chartView.data = d;
    this.setData(d);
    return this;
  }

  bind(store, mapFn) {
    this.chartView.bind(store, (state) => _capChartData(mapFn(state), this.maxPoints));
    return this;
  }
}

/**
 * BarChartCard
 */
export class BarChartCard extends ChartCard {
  constructor({
    title,
    height = 260,
    data = { labels: [], datasets: [] },
    options = {},
  } = {}) {
    const barOptions = {
      animation: false,
      plugins: {
        tooltip: { enabled: true },
        legend: { display: true },
      },
      ...options,
    };

    super({
      title,
      chart: { type: "bar", height, data, options: barOptions },
    });
  }
}

/**
 * PieChartCard
 * You said: "pie is same as doughnut" -> we default to doughnut.
 */
export class PieChartCard extends ChartCard {
  constructor({
    title,
    height = 260,
    data = { labels: [], datasets: [] },
    options = {},
    doughnut = true,
  } = {}) {
    const pieOptions = {
      animation: false,
      plugins: {
        tooltip: { enabled: true },
        legend: { display: true },
      },
      ...options,
    };

    super({
      title,
      chart: { type: doughnut ? "doughnut" : "pie", height, data, options: pieOptions },
    });
  }
}
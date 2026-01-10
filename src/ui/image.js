import { BaseElement } from "./base.js";

/**
 * ImageView
 * - raster images: <img>
 * - svg as <img> OR inline <svg> (string or fetched)
 *
 * Security note:
 * Inline SVG is basically HTML. If you inject untrusted SVG, you risk XSS.
 * This class removes <script> nodes, but that is NOT a full sanitizer.
 * Treat inline SVG as "trusted input only".
 */
import { ui } from "./ui.js";

export class ImageView extends BaseElement {
  constructor({
    src = null,
    alt = "",
    title = "",
    width = null,
    height = null,
    fit = "contain", // contain | cover | fill | none | scale-down
    inlineSvg = false, // when src is .svg: use inline fetch+parse
    className = "",
  } = {}) {
    super("div");
    this.el.className = `ui-image ${className}`.trim();

    this.img = ui.img().el;
    this.img.className = "ui-image-img";
    this.img.alt = alt ?? "";
    if (title) this.img.title = title;

    // Default styling (won't override user inline styles if you keep initStyle semantics)
    this.initStyle({
      display: "block",
    });

    // apply sizing
    this.setSize({ width, height });
    this.setFit(fit);

    this.el.appendChild(this.img);

    this._inlineHost = null; // container for inline svg
    this._mode = "img"; // "img" | "inline-svg"

    if (src) this.setSrc(src, { inlineSvg });
  }

  setFit(fit = "contain") {
    this.img.style.objectFit = fit;
    return this;
  }

  setSize({ width = null, height = null } = {}) {
    // Accept number => px, or string (e.g. "24px", "100%")
    const w = typeof width === "number" ? `${width}px` : width;
    const h = typeof height === "number" ? `${height}px` : height;

    if (w != null) this.el.style.width = w;
    if (h != null) this.el.style.height = h;

    // For <img> it helps to not overflow container
    this.img.style.maxWidth = "100%";
    this.img.style.maxHeight = "100%";
    return this;
  }

  /**
   * Set image source. For SVG you can choose:
   * - inlineSvg=false: keep <img src="...">
   * - inlineSvg=true: fetch + inline parse as <svg> so CSS/currentColor can apply
   */
  async setSrc(src, { inlineSvg = false } = {}) {
    if (!src) return this;

    const isSvg = typeof src === "string" && src.toLowerCase().includes(".svg");

    if (isSvg && inlineSvg) {
      await this.setSvgFromUrl(src);
      return this;
    }

    this._setModeImg();
    this.img.src = src;
    return this;
  }

  /**
   * Set inline SVG from a string containing <svg ...>...</svg>
   * Trusted input only.
   */
  setSvg(svgText) {
    if (!svgText) return this;

    const svgEl = this._parseSvg(svgText);
    this._setModeInlineSvg();
    this._inlineHost.replaceChildren(svgEl);
    return this;
  }

  /**
   * Fetch SVG from URL and inline it.
   */
  async setSvgFromUrl(url) {
    const res = await fetch(url, { credentials: "same-origin" });
    if (!res.ok) throw new Error(`ImageView: failed to fetch SVG (${res.status})`);
    const text = await res.text();
    this.setSvg(text);
    return this;
  }

  /**
   * Switch to <img> mode (raster and/or svg as file).
   */
  _setModeImg() {
    if (this._mode === "img") return;

    this._mode = "img";
    this._inlineHost?.remove();
    this._inlineHost = null;

    // restore <img>
    if (!this.img.isConnected) this.el.appendChild(this.img);
  }

  /**
   * Switch to inline <svg> mode.
   */
  _setModeInlineSvg() {
    if (this._mode === "inline-svg") return;

    this._mode = "inline-svg";

    // remove <img> (keeps it for later)
    if (this.img.isConnected) this.img.remove();

    if (!this._inlineHost) {
      this._inlineHost = ui.div().el;
      this._inlineHost.className = "ui-image-svg";
      this.el.appendChild(this._inlineHost);
    }
  }

  _parseSvg(svgText) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(svgText, "image/svg+xml");
    let svg = doc.documentElement;

    if (!svg || svg.nodeName.toLowerCase() !== "svg") {
      throw new Error("ImageView: invalid SVG (no <svg> root)");
    }

    // remove scripts (basic hardening; not a complete sanitizer!)
    doc.querySelectorAll("script").forEach((n) => n.remove());

    // Make it behave like an image inside its box
    svg.removeAttribute("width");
    svg.removeAttribute("height");
    svg.style.maxWidth = "100%";
    svg.style.maxHeight = "100%";
    svg.style.display = "block";

    return svg;
  }
}
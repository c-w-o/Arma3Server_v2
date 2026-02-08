import * as UI from "/ui-kit-0/src/ui-kit-0.js";

const formatAjvErrors = (errors = []) => {
  if (!Array.isArray(errors) || errors.length === 0) return "(no details)";
  return errors
    .map((e) => {
      const path = e.instancePath || "(root)";
      const msg = e.message || "invalid";
      return `${path} ${msg}`.trim();
    })
    .join("; ");
};

export class LauncherApiClient {
  constructor({ baseUrl = "", callTimeoutMs = 10000, retries = 2 } = {}) {
    this.rest = new UI.RestClient(baseUrl, { callTimeoutMs, retries });
    this.schemasLoaded = false;
    this.validators = {};
    this._initSchemas();
  }

  async _initSchemas() {
    try {
      const response = await fetch("/api_schemas.json");
      if (!response.ok) throw new Error(`Failed to fetch schemas: ${response.status}`);
      const schemasJson = await response.json();
      
      // Compile validators for each schema
      this.validators = {
        configsResponse: UI.makeValidator(schemasJson.properties.ConfigsResponse),
        configDetailResponse: UI.makeValidator(schemasJson.properties.ConfigDetailResponse),
        defaultsGetResponse: UI.makeValidator(schemasJson.properties.DefaultsGetResponse),
        defaultsUpdateRequest: UI.makeValidator(schemasJson.properties.DefaultsUpdateRequest),
        configOverrideRequest: UI.makeValidator(schemasJson.properties.ConfigOverrideRequest),
        actionResult: UI.makeValidator(schemasJson.properties.ActionResult),
        resolveModsRequest: UI.makeValidator(schemasJson.properties.ResolveModsRequest),
        resolveModsResponse: UI.makeValidator(schemasJson.properties.ResolveModsResponse),
        missionsResponse: UI.makeValidator(schemasJson.properties.MissionsResponse),
      };
      this.schemasLoaded = true;
    } catch (err) {
      console.error("[api] Failed to initialize schemas:", err);
      // Fallback: accept all (graceful degradation)
      this.validators = {
        configsResponse: () => ({ ok: true, errors: [], warning: "Schemas not loaded" }),
        configDetailResponse: () => ({ ok: true, errors: [], warning: "Schemas not loaded" }),
        defaultsGetResponse: () => ({ ok: true, errors: [], warning: "Schemas not loaded" }),
        defaultsUpdateRequest: () => ({ ok: true, errors: [], warning: "Schemas not loaded" }),
        configOverrideRequest: () => ({ ok: true, errors: [], warning: "Schemas not loaded" }),
        actionResult: () => ({ ok: true, errors: [], warning: "Schemas not loaded" }),
        resolveModsRequest: () => ({ ok: true, errors: [], warning: "Schemas not loaded" }),
        resolveModsResponse: () => ({ ok: true, errors: [], warning: "Schemas not loaded" }),
        missionsResponse: () => ({ ok: true, errors: [], warning: "Schemas not loaded" }),
      };
    }
  }

  _ensureObject(value, label) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw new Error(`${label} must be a JSON object`);
    }
  }

  _validate(validator, payload, label) {
    this._ensureObject(payload, label);
    const res = validator(payload);
    if (res.warning) {
      console.warn(`[api] ${label}: ${res.warning}`);
    }
    if (!res.ok) {
      const details = formatAjvErrors(res.errors);
      throw new Error(`${label} schema validation failed: ${details}`);
    }
  }

  _validateRequest(schemaKey, payload, label) {
    const validator = this.validators[schemaKey];
    if (!validator) throw new Error(`Missing validator for ${schemaKey}`);
    this._validate(validator, payload, label);
  }

  _validateResponse(schemaKey, payload, label) {
    const validator = this.validators[schemaKey];
    if (!validator) throw new Error(`Missing validator for ${schemaKey}`);
    this._validate(validator, payload, label);
  }

  async getConfigs() {
    const resp = await this.rest.get("/configs");
    this._validateResponse("configsResponse", resp, "GET /configs response");
    return resp;
  }

  async getConfigDetail(configName) {
    const safeName = encodeURIComponent(configName);
    const resp = await this.rest.get(`/config/${safeName}`);
    this._validateResponse("configDetailResponse", resp, "GET /config/{name} response");
    return resp;
  }

  async getDefaults() {
    const resp = await this.rest.get("/defaults");
    this._validateResponse("defaultsGetResponse", resp, "GET /defaults response");
    return resp;
  }

  async saveDefaults(payload) {
    this._validateRequest("defaultsUpdateRequest", payload, "POST /defaults request");
    const resp = await this.rest.post("/defaults", payload);
    this._validateResponse("actionResult", resp, "POST /defaults response");
    return resp;
  }

  async saveConfig(configName, payload) {
    this._validateRequest("configOverrideRequest", payload, "POST /config/{name} request");
    const safeName = encodeURIComponent(configName);
    const resp = await this.rest.post(`/config/${safeName}`, payload);
    this._validateResponse("actionResult", resp, "POST /config/{name} response");
    return resp;
  }

  async resolveModIds(modIds) {
    if (!Array.isArray(modIds) || modIds.length === 0) {
      throw new Error("modIds must be a non-empty array");
    }
    if (modIds.length > 100) {
      throw new Error("modIds must have at most 100 items");
    }
    
    const payload = { modIds };
    this._validateRequest("resolveModsRequest", payload, "POST /resolve-mod-ids request");
    const resp = await this.rest.post("/resolve-mod-ids", payload);
    this._validateResponse("resolveModsResponse", resp, "POST /resolve-mod-ids response");
    return resp;
  }

  async getMissions(configName = null) {
    const query = configName ? `?config=${encodeURIComponent(configName)}` : "";
    const resp = await this.rest.get(`/missions${query}`);
    this._validateResponse("missionsResponse", resp, "GET /missions response");
    return resp;
  }

  async saveMissionMeta(payload) {
    this._ensureObject(payload, "MissionMetaPayload");
    const resp = await this.rest.post("/missions", payload);
    return resp;
  }

  async uploadMission({ file, configName, missionName, description }) {
    if (!file) throw new Error("file is required");
    if (!configName) throw new Error("configName is required");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("configName", configName);
    if (missionName) formData.append("missionName", missionName);
    if (description) formData.append("description", description);

    const resp = await fetch("/missions/upload", {
      method: "POST",
      body: formData,
    });

    if (!resp.ok) {
      let err = null;
      try {
        err = await resp.json();
      } catch {
        err = null;
      }
      return { ok: false, detail: err?.detail || `Upload failed (${resp.status})` };
    }
    return await resp.json();
  }

  // ========== Workshop Updates ==========

  async getWorkshopUpdates(configName) {
    const safeName = encodeURIComponent(configName);
    const resp = await this.rest.get(`/config/${safeName}/workshop/updates`);
    return resp;
  }

  async updateWorkshopItems(configName, items, { validate = false } = {}) {
    if (!Array.isArray(items) || items.length === 0) {
      throw new Error("items must be a non-empty array");
    }
    const safeName = encodeURIComponent(configName);
    const payload = { items, validate: !!validate };
    const resp = await this.rest.post(`/config/${safeName}/workshop/updates`, payload);
    return resp;
  }

  // ========== Variants API ==========

  async getDefaultsMods() {
    const resp = await this.rest.get("/api/defaults/mods");
    return resp;
  }

  async getVariants() {
    const resp = await this.rest.get("/api/variants");
    return resp;
  }

  async getVariant(name) {
    const safeName = encodeURIComponent(name);
    const resp = await this.rest.get(`/api/variants/${safeName}`);
    return resp;
  }

  async createVariant(name, payload = {}) {
    const safeName = encodeURIComponent(name);
    const resp = await this.rest.post(`/api/variants?name=${safeName}`, payload);
    return resp;
  }

  async updateVariantMods(name, payload) {
    const safeName = encodeURIComponent(name);
    const resp = await this.rest.put(`/api/variants/${safeName}/mods`, payload);
    return resp;
  }

  async deleteVariant(name) {
    const safeName = encodeURIComponent(name);
    const resp = await this.rest.delete(`/api/variants/${safeName}`);
    return resp;
  }
}

export const apiClient = new LauncherApiClient({
  baseUrl: "",
  callTimeoutMs: 10000,
  retries: 2,
});

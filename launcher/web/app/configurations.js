import * as UI from "/ui-kit-0/src/ui-kit-0.js";

// Create REST client for API calls
const rpcClient = new UI.RestClient("", {
    callTimeoutMs: 10000,
    retries: 2,
});

export function createConfigurationsContent() {
    const container = new UI.VDiv({ gap: 12 });
    
    // State
    let selectedConfigName = null;
    let configData = null;
    
    // Get global store
    const globalStore = UI.AppMain.getInstance()._store;
    
    // Header
    const headerRow = new UI.HDiv({ gap: 12, align: "center" });
    headerRow.add(
        new UI.Heading("Konfigurationen", { level: 3 })
    );
    container.add(headerRow);
    
    // Main layout: List on left, Editor on right
    const mainLayout = new UI.HDiv({ gap: 12 });
    mainLayout.setStyle({ display: "flex", gap: "12px" });
    
    // === LEFT: Configuration List ===
    const listDiv = new UI.VDiv({ gap: 8 });
    listDiv.setStyle({
        flex: "0 0 250px",
        background: "var(--ui-color-surface)",
        border: "1px solid var(--ui-color-border)",
        borderRadius: "var(--ui-radius-md)",
        padding: "12px",
        maxHeight: "600px",
        overflowY: "auto"
    });
    
    listDiv.add(
        new UI.Heading("Verfügbare Configs", { level: 4 }).setStyle({ margin: "0 0 8px 0" })
    );
    
    const configList = new UI.VDiv({ gap: 4 });
    listDiv.add(configList);
    const configButtons = new Map();
    
    mainLayout.add(listDiv);
    
    // === RIGHT: Editor Tabs ===
    const editorDiv = new UI.VDiv({ gap: 12 });
    editorDiv.setStyle({ flex: "1" });
    
    const tabs = new UI.Tabs();
    
    // Placeholder content (wird später gefüllt)
    const basisContent = new UI.VDiv({ gap: 8 }).add(
        new UI.Text("Laden...")
    );
    
    const overridesContent = new UI.VDiv({ gap: 8 }).add(
        new UI.Text("Laden...")
    );
    
    const previewContent = new UI.VDiv({ gap: 8 }).add(
        new UI.Text("Laden...")
    );
    
    tabs.addTab("basis", "Basis", basisContent);
    tabs.addTab("overrides", "Overrides", overridesContent);
    tabs.addTab("merged", "Merged", previewContent);
    
    editorDiv.add(tabs);
    
    mainLayout.add(editorDiv);
    container.add(mainLayout);
    
    // Bottom: Save/Cancel
    const saveBtn = new UI.Button("Save").setStyle({ padding: "8px 16px" });
    const cancelBtn = new UI.Button("Cancel").setStyle({ padding: "8px 16px", background: "var(--ui-color-surface)", color: "var(--ui-color-text)" });
    
    container.add(
        new UI.HDiv({ gap: 8 }).add(saveBtn, cancelBtn)
    );
    
    // === API Integration ===
    
    // Load all configs list
    async function loadConfigsList() {
        try {
            const resp = await rpcClient.get("/configs");
            if (!resp.ok) throw new Error(resp.detail || "Failed to load configs");
            
            configList.el.innerHTML = ""; // Clear
            configButtons.clear();
            
            for (const cfg of resp.configs) {
                const btn = new UI.Button(cfg.name).setStyle({ width: "100%", textAlign: "left" });
                btn.el.addEventListener("click", () => loadConfigDetail(cfg.name, { manual: true }));
                configButtons.set(cfg.name, btn);
                configList.add(btn);
            }
            
            // Auto-select first loadable config
            for (const cfg of resp.configs) {
                const ok = await loadConfigDetail(cfg.name, { manual: false, silent: true });
                if (ok) break;
            }
        } catch (err) {
            console.error("Failed to load configs:", err);
            configList.add(new UI.Text(`Fehler: ${err.message}`));
        }
    }
    
    // Load config detail with defaults, overrides, merged
    async function loadConfigDetail(configName, { manual = false, silent = false } = {}) {
        try {
            selectedConfigName = configName;
            const resp = await rpcClient.get(`/config/${encodeURIComponent(configName)}`);
            if (!resp.ok) throw new Error(resp.detail || "Failed to load config");
            
            configData = resp;
            _markSelected(configName);
            
            // Clear and rebuild Basis tab
            basisContent.el.innerHTML = "";
            basisContent.add(
                new UI.Heading("Basis-Konfiguration (Defaults)", { level: 4 }).setStyle({ margin: "0" }),
                new UI.Text("Diese Einstellungen gelten für alle Konfigurationen.").setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)" }),
                resp.defaults.dlcs && resp.defaults.dlcs.length > 0 ? _buildDlcsSection("Basis DLCs", resp.defaults.dlcs) : new UI.Text("Keine DLCs"),
                _buildModsTable("Basis Mods", resp.defaults.mods)
            );
            
            // Clear and rebuild Overrides tab
            overridesContent.el.innerHTML = "";
            overridesContent.add(
                new UI.Heading("Config-spezifische Overrides", { level: 4 }).setStyle({ margin: "0" }),
                new UI.Text(`Änderungen gegen die Basis-Konfiguration für "${configName}".`).setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)" }),
                resp.overrides.dlcs && resp.overrides.dlcs.length > 0 ? _buildDlcsSection("Override DLCs", resp.overrides.dlcs) : new UI.Text("Keine DLC-Änderungen"),
                _buildModsTable("Override Mods", resp.overrides.mods)
            );
            
            // Clear and rebuild Merged tab
            previewContent.el.innerHTML = "";
            previewContent.add(
                new UI.Heading("Merged Preview", { level: 4 }).setStyle({ margin: "0" }),
                new UI.Text("Kombinierte Konfiguration (Basis + Overrides).").setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)" }),
                resp.merged.dlcs && resp.merged.dlcs.length > 0 ? _buildDlcsSection("Merged DLCs", resp.merged.dlcs) : new UI.Text("Keine DLCs"),
                _buildModsTable("Merged Mods", resp.merged.mods)
            );
            
            return true;
        } catch (err) {
            if (!silent) {
                console.error("Failed to load config detail:", err);
                basisContent.el.innerHTML = `<div style="color: red;">Fehler: ${err.message}</div>`;
            }
            return false;
        }
    }

    function _markSelected(name) {
        for (const [cfg, btn] of configButtons.entries()) {
            btn.setStyle({ background: cfg === name ? "var(--ui-color-nav-active)" : "" });
        }
    }
    
    // Helper: Build mods table from mods object
    function _buildModsTable(title, modsObj) {
        const rows = [];
        const modDetailMap = new Map(); // Map category -> items for later lookup
        
        for (const [category, items] of Object.entries(modsObj)) {
            if (items && items.length > 0) {
                modDetailMap.set(category, items);
                rows.push({
                    category,
                    count: items.length
                });
            }
        }
        
        // Container für Tabelle + Details
        const container = new UI.VDiv({ gap: 12 });
        
        // Mods-Tabelle
        const table = new UI.Table({
            columns: [
                { label: "Kategorie", key: "category" },
                { label: "Anzahl", key: "count" }
            ],
            data: rows.length > 0 ? rows : [{ category: "(leer)", count: 0 }]
        });
        table.setStyle({ width: "100%", fontSize: "0.9em", cursor: "pointer" });
        
        // Details-Container (versteckt bis eine Zeile geklickt wird)
        const detailsContainer = new UI.VDiv({ gap: 8 });
        detailsContainer.setStyle({ display: "none" });
        
        // Event-Handler für Row-Clicks
        table.el.addEventListener("click", (e) => {
            const row = e.target.closest("tr");
            if (!row) return;
            
            // Finde die Kategorie aus der geklickten Zeile
            const cells = row.querySelectorAll("td");
            if (cells.length === 0) return;
            
            const category = cells[0].textContent.trim();
            const items = modDetailMap.get(category);
            
            if (items) {
                // Zeige Details
                detailsContainer.el.style.display = "block";
                detailsContainer.el.innerHTML = "";
                
                // Baue Details als Liste von Reihen mit Links
                const detailsDiv = new UI.VDiv({ gap: 4 });
                
                for (const mod of items) {
                    const steamUrl = `https://steamcommunity.com/sharedfiles/filedetails/?id=${mod.id}`;
                    
                    const row = new UI.HDiv({ gap: 8, align: "center" }).setStyle({
                        padding: "4px 8px",
                        borderBottom: "1px solid var(--ui-color-border)",
                        fontSize: "0.85em"
                    });
                    
                    const nameSpan = new UI.Span(mod.name).setStyle({ flex: "1" });
                    const idSpan = new UI.Span(`(${mod.id})`).setStyle({ minWidth: "120px", textAlign: "right", color: "var(--ui-color-text-muted)" });
                    
                    const steamLink = new UI.Link("🔗", steamUrl, { 
                        target: "_blank",
                        title: "Steam Workshop öffnen"
                    }).setStyle({
                        textDecoration: "none",
                        cursor: "pointer"
                    });
                    
                    row.add(nameSpan, idSpan, steamLink);
                    detailsDiv.add(row);
                }
                
                detailsContainer.add(
                    new UI.Heading(`${category} - Details`, { level: 5 }).setStyle({ margin: "0 0 6px 0" }),
                    detailsDiv
                );
            }
        });
        
        container.add(
            new UI.Heading("Mods", { level: 5 }).setStyle({ margin: "0 0 6px 0" }),
            table,
            detailsContainer
        );
        
        return container;
    }
    
    // Helper: Build DLCs section
    function _buildDlcsSection(title, dlcList) {
        return new UI.VDiv({ gap: 8 }).add(
            new UI.Heading("DLCs", { level: 5 }).setStyle({ margin: "0 0 6px 0" }),
            new UI.Text(dlcList && dlcList.length > 0 ? dlcList.join(", ") : "(keine)").setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)" })
        );
    }
    
    // Save button handler
    saveBtn.el.addEventListener("click", async () => {
        if (!selectedConfigName) {
            alert("Bitte wählen Sie eine Konfiguration aus");
            return;
        }
        
        try {
            // For now, send back the override data as-is
            const overridePayload = configData.overrides;
            
            const resp = await rpcClient.post(`/config/${encodeURIComponent(selectedConfigName)}`, overridePayload);
            if (!resp.ok) throw new Error(resp.detail || "Failed to save");
            
            alert("Konfiguration gespeichert!");
            await loadConfigsList(); // Refresh
        } catch (err) {
            console.error("Failed to save config:", err);
            alert(`Fehler beim Speichern: ${err.message}`);
        }
    });
    
    // Cancel button handler
    cancelBtn.el.addEventListener("click", () => {
        if (selectedConfigName) {
            loadConfigDetail(selectedConfigName); // Reload
        }
    });
    
    // Initial load
    loadConfigsList();
    
    return container;
}

import * as UI from "/ui-kit-0/src/ui-kit-0.js";
import { apiClient } from "./api/client.js";

export function createConfigurationsContent() {
    const container = new UI.VDiv({ gap: 12 });
    
    // State
    let selectedConfigName = null;
    let configData = null;
    let isEditMode = false; // Toggle für Edit-Modus
    let editState = {
        modsToDelete: new Set(), // IDs markiert zum Löschen
        modsToAdd: [], // Array von {id, name} zum Hinzufügen
        selectedDlc: null // Welche DLC ist ausgewählt
    };
    
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
    // Sidebar wird durch Dropdown ersetzt -> nicht hinzufügen
    // mainLayout.add(listDiv);
    
    // === RIGHT: Editor Tabs ===
    const editorDiv = new UI.VDiv({ gap: 12 });
    editorDiv.setStyle({ flex: "1" });
    
    const tabs = new UI.Tabs();

    // Config-Auswahl (Dropdown) links von den Tabs platzieren
    const configSelect = new UI.Select({ options: [], value: "" });
    configSelect.setStyle({ minWidth: "220px" });

    // Neue Konfiguration Button
    const createConfigBtn = new UI.Button("➕ Neu").setStyle({
        padding: "6px 10px",
        fontSize: "0.85em",
        whiteSpace: "nowrap"
    });

    tabs.group.bar.add(configSelect, createConfigBtn);
    
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
    
    const editContent = new UI.VDiv({ gap: 8 }).add(
        new UI.Text("Laden...")
    );
    
    tabs.addTab("basis", "Basis", basisContent);
    tabs.addTab("overrides", "Overrides", overridesContent);
    tabs.addTab("merged", "Merged", previewContent);
    tabs.addTab("edit", "Edit", editContent);
    
    // Dropdown-Change Handler: Konfiguration, Variante oder Basis laden
    configSelect.on("change", async () => {
        const val = configSelect.getValue();
        if (val === "BASE_MODS_VIEW") {
            await loadBaseMods();
        } else if (val && val.startsWith("variant:")) {
            const variantName = val.substring(8);
            await loadVariant(variantName, { manual: true, silent: false });
        } else if (val && val.startsWith("config:")) {
            const configName = val.substring(7);
            await loadConfigDetail(configName, { manual: true, silent: false });
        }
    });
    
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

    async function createNewConfig() {
        try {
            const rawName = prompt("Name der neuen Konfiguration:");
            if (rawName === null) return; // user cancelled
            const name = String(rawName || "").trim();
            if (!name) {
                alert("Bitte einen gültigen Namen eingeben");
                return;
            }
            if (/[\\/]/.test(name)) {
                alert("Der Name darf keine Slash-Zeichen enthalten");
                return;
            }

            const rawDesc = prompt("Beschreibung (optional):") ?? "";
            const description = String(rawDesc || "").trim();

            // Prevent duplicates
            const existing = await apiClient.getConfigs();
            if (existing.ok && Array.isArray(existing.configs)) {
                const names = existing.configs.map(c => c.name);
                if (names.includes(name)) {
                    alert(`Konfiguration "${name}" existiert bereits`);
                    return;
                }
            }

            // Create minimal override (description optional)
            const payload = description ? { description } : {};
            const resp = await apiClient.saveConfig(name, payload);
            if (!resp.ok) throw new Error(resp.detail || "Fehler beim Erstellen");

            selectedConfigName = `config:${name}`;
            await loadConfigsList();
        } catch (err) {
            console.error("Failed to create config:", err);
            alert(`Fehler beim Erstellen: ${err.message}`);
        }
    }
    
    // Load all configs list
    async function loadConfigsList() {
        try {
            const resp = await apiClient.getConfigs();
            if (!resp.ok) throw new Error(resp.detail || "Failed to load configs");
            
            // Build dropdown options
            const options = [{ label: "─── Basis ───", value: "BASE_MODS_VIEW" }];
            for (const cfg of resp.configs) options.push({ label: `  ${cfg.name}`, value: `config:${cfg.name}` });
            
            // Load variants
            const varResp = await apiClient.getVariants();
            if (varResp.ok && varResp.data.variants && varResp.data.variants.length > 0) {
                options.push({ label: "─── Varianten ───", value: "SEPARATOR", disabled: true });
                for (const variant of varResp.data.variants) {
                    options.push({ label: `  ${variant.name}`, value: `variant:${variant.name}` });
                }
            }
            
            configSelect.setOptions(options);
            
            // Auto-select: prefer previously selected
            if (selectedConfigName) {
                configSelect.setValue(selectedConfigName);
                if (selectedConfigName === "BASE_MODS_VIEW") {
                    await loadBaseMods();
                } else if (selectedConfigName.startsWith("variant:")) {
                    const variantName = selectedConfigName.substring(8);
                    await loadVariant(variantName, { manual: false, silent: true });
                } else if (selectedConfigName.startsWith("config:")) {
                    const configName = selectedConfigName.substring(7);
                    await loadConfigDetail(configName, { manual: false, silent: true });
                }
            } else {
                // Try load first config; fallback to BASE_MODS_VIEW
                let loaded = false;
                for (const cfg of resp.configs) {
                    const ok = await loadConfigDetail(cfg.name, { manual: false, silent: true });
                    if (ok) { configSelect.setValue(`config:${cfg.name}`); loaded = true; break; }
                }
                if (!loaded) {
                    selectedConfigName = "BASE_MODS_VIEW";
                    configSelect.setValue("BASE_MODS_VIEW");
                    await loadBaseMods();
                }
            }
        } catch (err) {
            console.error("Failed to load configs:", err);
            // Show error in preview panel
            while (previewContent.el.firstChild) previewContent.el.firstChild.remove();
            previewContent.add(new UI.Text(`Fehler: ${err.message}`));
        }
    }

    createConfigBtn.el.addEventListener("click", createNewConfig);
    
    // Load config detail with defaults, overrides, merged
    async function loadConfigDetail(configName, { manual = false, silent = false } = {}) {
        try {
            selectedConfigName = `config:${configName}`;
            const resp = await apiClient.getConfigDetail(configName);
            if (!resp.ok) throw new Error(resp.detail || "Failed to load config");
            
            configData = resp;
            _markSelected(`config:${configName}`);
            
            // Clear and rebuild Basis tab
            while (basisContent.el.firstChild) basisContent.el.firstChild.remove();
            basisContent.add(
                new UI.Heading("Basis-Konfiguration (Defaults)", { level: 4 }).setStyle({ margin: "0" }),
                new UI.Text("Diese Einstellungen gelten für alle Konfigurationen.").setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)" }),
                resp.defaults.dlcs && resp.defaults.dlcs.length > 0 ? _buildDlcsSection("Basis DLCs", resp.defaults.dlcs) : new UI.Text("Keine DLCs"),
                _buildModsTable("Basis Mods", resp.defaults.mods)
            );
            
            // Clear and rebuild Overrides tab
            while (overridesContent.el.firstChild) overridesContent.el.firstChild.remove();
            overridesContent.add(
                new UI.Heading("Config-spezifische Overrides", { level: 4 }).setStyle({ margin: "0" }),
                new UI.Text(`Änderungen gegen die Basis-Konfiguration für "${configName}".`).setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)" }),
                resp.overrides.dlcs && resp.overrides.dlcs.length > 0 ? _buildDlcsSection("Override DLCs", resp.overrides.dlcs) : new UI.Text("Keine DLC-Änderungen"),
                _buildModsTable("Override Mods", resp.overrides.mods)
            );
            
            // Clear and rebuild Merged tab
            while (previewContent.el.firstChild) previewContent.el.firstChild.remove();
            previewContent.add(
                new UI.Heading("Merged Preview", { level: 4 }).setStyle({ margin: "0" }),
                new UI.Text("Kombinierte Konfiguration (Basis + Overrides).").setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)" }),
                resp.merged.dlcs && resp.merged.dlcs.length > 0 ? _buildDlcsSection("Merged DLCs", resp.merged.dlcs) : new UI.Text("Keine DLCs"),
                _buildModsTable("Merged Mods", resp.merged.mods)
            );
            
            // Clear and rebuild Edit tab mit Checkboxes, Textarea und Radio-Buttons
            while (editContent.el.firstChild) editContent.el.firstChild.remove();
            editState.modsToDelete = new Set();
            editState.modsToAdd = [];
            editState.selectedDlc = resp.merged.dlcs && resp.merged.dlcs.length > 0 ? resp.merged.dlcs[0] : null;
            
            editContent.add(
                new UI.Heading("Edit Configuration", { level: 4 }).setStyle({ margin: "0" }),
                _buildEditDlcsSection(resp.merged.dlcs && resp.merged.dlcs.length > 0 ? resp.merged.dlcs[0] : null),
                _buildEditModsSection(resp.merged.mods)
            );
            
            return true;
        } catch (err) {
            if (!silent) {
                console.error("Failed to load config detail:", err);
                while (basisContent.el.firstChild) basisContent.el.firstChild.remove();
                basisContent.add(new UI.Text(`Fehler: ${err.message}`).setStyle({ color: "red" }));
            }
            return false;
        }
    }

    function _markSelected(name) {
        // Sync dropdown selection
        if (name) configSelect.setValue(name);
    }
    
    // Helper: Build mods table from mods object
    function _buildModsTable(title, modsObj) {
        const rows = [];
        const modDetailMap = new Map(); // Map category -> items for later lookup
        const displayedIds = new Set(); // Dedupe über Kategorien hinweg
        
        // Kategorien in fester Reihenfolge (höchste Prio zuerst)
        const categoryOrder = ["serverMods", "baseMods", "clientMods", "maps", "missionMods"];
        
        for (const category of categoryOrder) {
            const items = modsObj[category];
            if (items && items.length > 0) {
                // Filtere bereits angezeigte Mods aus
                const uniqueItems = items.filter(mod => !displayedIds.has(mod.id));
                
                // Merke IDs für zukünftige Kategorien
                for (const mod of items) {
                    displayedIds.add(mod.id);
                }
                
                modDetailMap.set(category, uniqueItems);
                
                if (uniqueItems.length > 0) {
                    rows.push({
                        category,
                        count: uniqueItems.length
                    });
                }
            }
        }
        
        // Restliche Kategorien (falls vorhanden, aber nicht in categoryOrder)
        for (const [category, items] of Object.entries(modsObj)) {
            if (!categoryOrder.includes(category) && items && items.length > 0) {
                const uniqueItems = items.filter(mod => !displayedIds.has(mod.id));
                for (const mod of items) {
                    displayedIds.add(mod.id);
                }
                modDetailMap.set(category, uniqueItems);
                if (uniqueItems.length > 0) {
                    rows.push({
                        category,
                        count: uniqueItems.length
                    });
                }
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
                while (detailsContainer.el.firstChild) detailsContainer.el.firstChild.remove();
                
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
    
    // Helper: Build variant override view (shows added/removed/replace)
    function _buildVariantOverrideView(override) {
        const container = new UI.VDiv({ gap: 12 });
        
        const categories = [
            { key: "serverMods", label: "Server Mods" },
            { key: "baseMods", label: "Base Mods" },
            { key: "clientMods", label: "Client Mods" },
            { key: "maps", label: "Maps" },
            { key: "missionMods", label: "Mission Mods" }
        ];
        
        let hasOverrides = false;
        
        categories.forEach(cat => {
            const catOverride = override[cat.key];
            if (!catOverride) return;
            
            const added = catOverride.added || [];
            const removed = catOverride.removed || [];
            const replace = catOverride.replace;
            
            if (replace) {
                hasOverrides = true;
                container.add(
                    new UI.Heading(`${cat.label} (REPLACE)`, { level: 5 }).setStyle({ 
                        margin: "8px 0 4px 0", 
                        color: "var(--ui-color-warning)" 
                    }),
                    new UI.Text(`Kompletter Ersatz mit ${replace.length} Mods`).setStyle({ fontSize: "0.9em" })
                );
                
                // Show replace mods
                const replaceDiv = new UI.VDiv({ gap: 2 });
                replace.forEach(m => {
                    replaceDiv.add(
                        new UI.Text(`  • ${m.name || "N/A"} (${m.id})`).setStyle({ fontSize: "0.85em" })
                    );
                });
                container.add(replaceDiv);
            } else if (added.length > 0 || removed.length > 0) {
                hasOverrides = true;
                container.add(new UI.Heading(cat.label, { level: 5 }).setStyle({ margin: "8px 0 4px 0" }));
                
                if (added.length > 0) {
                    const addedDiv = new UI.VDiv({ gap: 2 });
                    addedDiv.add(
                        new UI.Text(`➕ Hinzugefügt: ${added.length}`).setStyle({ 
                            color: "var(--ui-color-success)", 
                            fontSize: "0.9em",
                            fontWeight: "bold"
                        })
                    );
                    added.forEach(m => {
                        addedDiv.add(
                            new UI.Text(`  • ${m.name || "N/A"} (${m.id})`).setStyle({ fontSize: "0.85em" })
                        );
                    });
                    container.add(addedDiv);
                }
                
                if (removed.length > 0) {
                    const removedDiv = new UI.VDiv({ gap: 2 });
                    removedDiv.add(
                        new UI.Text(`➖ Entfernt: ${removed.length} IDs`).setStyle({ 
                            color: "var(--ui-color-error)", 
                            fontSize: "0.9em",
                            fontWeight: "bold"
                        })
                    );
                    removedDiv.add(
                        new UI.Text(`  ${removed.join(", ")}`).setStyle({ fontSize: "0.85em" })
                    );
                    container.add(removedDiv);
                }
            }
        });
        
        if (!hasOverrides) {
            container.add(
                new UI.Text("Keine Overrides definiert").setStyle({ 
                    fontStyle: "italic", 
                    color: "var(--ui-color-text-muted)" 
                })
            );
        }
        
        return container;
    }
    
    // Helper: Build Edit DLCs section with radio buttons - Grid Layout
    function _buildEditDlcsSection(currentDlc) {
        const container = new UI.VDiv({ gap: 12 });
        container.add(new UI.Heading("DLCs (Auswahl)", { level: 5 }).setStyle({ margin: "0 0 12px 0" }));
        
        // Alle verfügbaren DLCs (aus Backend DLC-Mapping)
        const allDlcs = [
            "Keine",
            "Contact",
            "CSLA Iron Curtain",
            "Global Mobilization",
            "Western Sahara",
            "S.O.G. Prairie Fire",
            "Spearhead 1944",
            "Reaction Forces",
            "Expeditionary Forces"
        ];
        
        // RadioGroup erstellen (normalisierte Auswahl)
        const normalize = (val) => String(val || "")
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "");

        let initialValue = "Keine";
        if (currentDlc) {
            const norm = normalize(currentDlc);
            const match = allDlcs.find(d => normalize(d) === norm);
            initialValue = match || currentDlc;
        }
        const radioGroup = new UI.RadioGroup({
            name: "dlc-selection",
            options: allDlcs,
            selected: initialValue,
            layout: "grid"
        });
        
        // Visuelle Darstellung aktualisieren + initial state (map 'Keine' -> null)
        radioGroup.setValue(initialValue);
        editState.selectedDlc = initialValue === "Keine" ? null : initialValue;
        console.log("Initial DLC selection:", initialValue, "mapped to", editState.selectedDlc);

        radioGroup.on("change", (e) => {
            if (e.detail && e.detail.value) {
                const val = e.detail.value;
                editState.selectedDlc = (val === "Keine") ? null : val;
                console.log("Selected DLC via radio change:", val, "mapped to", editState.selectedDlc);
            }
        });
        
        container.add(radioGroup);
        return container;
    }
    
    // Helper: Build Edit Mods section with 5 category tables, inputs, and minus-mods
    function _buildEditModsSection(mergedMods) {
        const container = new UI.VDiv({ gap: 20 });
        
        // Bestimme welche Mods aus der Basis kommen (für Checkbox-Logik)
        const isBasisView = selectedConfigName === "BASE_MODS_VIEW";
        const baseModIds = new Set();
        const defaultsMods = (configData && configData.defaults && configData.defaults.mods) ? configData.defaults.mods : mergedMods;
        for (const [cat, items] of Object.entries(defaultsMods)) {
            if (items) for (const mod of items) baseModIds.add(mod.id);
        }
        // Dedupe Anzeige über Kategorien hinweg (Prio: serverMods, baseMods, clientMods, maps, missionMods)
        const displayedIds = new Set();
        
        // Die 5 Kategorien - in dieser Reihenfolge anzeigen
        const categories = ["serverMods", "baseMods", "clientMods", "maps", "missionMods"];
        const categoryLabels = {
            serverMods: "Server Mods",
            baseMods: "Base Mods",
            clientMods: "Client Mods",
            maps: "Maps",
            missionMods: "Mission Mods"
        };
        
        // Für jede Kategorie eine Tabelle + Input
        for (const category of categories) {
            const items = (mergedMods[category] || []).filter(mod => !displayedIds.has(mod.id));
            
            // Kategorie-Container
            const catContainer = new UI.VDiv({ gap: 8 });
            catContainer.setStyle({
                border: "1px solid var(--ui-color-border)",
                borderRadius: "var(--ui-radius-md)",
                padding: "12px",
                background: "var(--ui-color-surface)"
            });
            
            // Kategorie-Titel
            catContainer.add(
                new UI.Heading(categoryLabels[category], { level: 5 }).setStyle({ margin: "0 0 12px 0" })
            );
            
            // Input-Feld mit Buttons (Resolve + Add)
            const inputRow = new UI.HDiv({ gap: 8, align: "stretch" });
            
            const textarea = new UI.TextArea("", { placeholder: "IDs oder Steam-Links (eine pro Zeile)", rows: 3 });
            textarea.setStyle({ flex: "1", padding: "8px", fontFamily: "monospace", fontSize: "0.85em" });
            
            const btnContainer = new UI.VDiv({ gap: 4 });
            btnContainer.setStyle({ minWidth: "120px" });
            
            const resolveBtn = new UI.Button("Resolve").setStyle({
                padding: "8px 12px",
                fontSize: "0.85em",
                width: "100%",
                whiteSpace: "nowrap"
            });
            
            const addBtn = new UI.Button("Add Mods").setStyle({
                padding: "8px 12px",
                fontSize: "0.85em",
                width: "100%",
                whiteSpace: "nowrap"
            });
            
            btnContainer.add(resolveBtn, addBtn);
            inputRow.add(textarea, btnContainer);
            
            // Resolved mods display area
            const resolvedArea = new UI.VDiv({ gap: 4 });
            resolvedArea.setStyle({ display: "none" });
            
            // Store resolved mods for this category
            let resolvedMods = {};
            
            resolveBtn.el.addEventListener("click", async () => {
                const text = textarea.el.value.trim();
                if (!text) {
                    alert("Bitte geben Sie mindestens eine Mod-ID ein");
                    return;
                }
                
                const lines = text.split("\n").map(l => l.trim()).filter(l => l.length > 0);
                const modIds = [];
                for (const line of lines) {
                    const modId = _extractModId(line);
                    if (modId) modIds.push(modId);
                }
                
                if (modIds.length === 0) {
                    alert("Keine gültigen Mod-IDs gefunden");
                    return;
                }
                
                // Show loading state
                resolveBtn.el.disabled = true;
                resolveBtn.setText("Resolving...");
                resolvedArea.el.style.display = "block";
                resolvedArea.el.innerHTML = "";
                resolvedArea.add(new UI.Text("🔄 Resolving mod names from Steam..."));
                
                try {
                    const result = await apiClient.resolveModIds(modIds);
                    
                    // Clear and rebuild resolved list
                    resolvedArea.el.innerHTML = "";
                    
                    if (!result.ok) {
                        resolvedArea.add(new UI.Text(`❌ Error: ${result.detail || "Unknown error"}`));
                        return;
                    }
                    
                    // Store resolved data
                    resolvedMods = result.mods || {};
                    
                    const resolvedList = new UI.VDiv({ gap: 2 });
                    resolvedList.setStyle({
                        border: "1px solid var(--ui-color-border)",
                        borderRadius: "var(--ui-radius-sm)",
                        padding: "8px",
                        background: "var(--ui-color-surface)",
                        maxHeight: "200px",
                        overflowY: "auto"
                    });
                    
                    for (const [modId, modData] of Object.entries(resolvedMods)) {
                        const row = new UI.HDiv({ gap: 8, align: "center" }).setStyle({
                            padding: "4px 6px",
                            borderBottom: "1px solid var(--ui-color-border, rgba(0,0,0,0.05))",
                            fontSize: "0.85em"
                        });
                        
                        // Status icon
                        let statusIcon = "✓";
                        if (modData.error) statusIcon = "⚠️";
                        else if (modData.source === "local") statusIcon = "📁";
                        else if (modData.source === "steam") statusIcon = "🌐";
                        
                        row.add(new UI.Span(statusIcon).setStyle({ minWidth: "20px" }));
                        
                        // Name
                        const nameSpan = new UI.Span(modData.name).setStyle({ flex: "1" });
                        row.add(nameSpan);
                        
                        // ID (small)
                        row.add(new UI.Span(`(${modId})`).setStyle({ color: "var(--ui-color-text-muted)", fontSize: "0.8em" }));
                        
                        resolvedList.add(row);
                    }
                    
                    resolvedArea.el.innerHTML = "";
                    resolvedArea.add(
                        new UI.Text("✓ Resolved - Click 'Add Mods' to add them:").setStyle({ fontSize: "0.85em", fontWeight: "bold", color: "var(--ui-color-success, green)" }),
                        resolvedList
                    );
                } catch (err) {
                    console.error("Error resolving mods:", err);
                    resolvedArea.el.innerHTML = "";
                    resolvedArea.add(new UI.Text(`❌ Error: ${err.message}`));
                } finally {
                    resolveBtn.el.disabled = false;
                    resolveBtn.setText("Resolve");
                }
            });
            
            addBtn.el.addEventListener("click", () => {
                // Use resolved mods if available, otherwise extract from textarea
                let added = 0;
                
                if (Object.keys(resolvedMods).length > 0) {
                    // Add resolved mods with proper names
                    for (const [modId, modData] of Object.entries(resolvedMods)) {
                        const alreadyExists = editState.modsToAdd.some(m => String(m.id) === String(modId) && m.category === category);
                        if (!alreadyExists) {
                            editState.modsToAdd.push({ 
                                id: modId, 
                                name: modData.name || `Mod ${modId}`, 
                                category: category 
                            });
                            added++;
                            console.log("Added resolved mod to", category, ":", modId, modData.name);
                        }
                    }
                    
                    // Clear textarea and resolved area
                    textarea.el.value = "";
                    resolvedMods = {};
                    resolvedArea.el.style.display = "none";
                } else {
                    // Fallback: extract IDs from textarea
                    const text = textarea.el.value.trim();
                    if (!text) {
                        alert("Bitte geben Sie mindestens eine Mod-ID ein oder klicken Sie zuerst auf 'Resolve'");
                        return;
                    }
                    
                    const lines = text.split("\n").map(l => l.trim()).filter(l => l.length > 0);
                    for (const line of lines) {
                        const modId = _extractModId(line);
                        if (modId) {
                            const alreadyExists = editState.modsToAdd.some(m => String(m.id) === String(modId) && m.category === category);
                            if (!alreadyExists) {
                                editState.modsToAdd.push({ id: modId, name: `Mod ${modId}`, category: category });
                                added++;
                                console.log("Added mod to", category, ":", modId);
                            }
                        }
                    }
                    textarea.el.value = "";
                }
                
                if (added > 0) {
                    updatePendingDisplay();
                    alert(`${added} Mod(s) zu ${categoryLabels[category]} hinzugefügt`);
                } else {
                    alert("Keine neuen Mods hinzugefügt (evtl. bereits vorhanden)");
                }
            });
            
            catContainer.add(inputRow, resolvedArea);
            catContainer.add(new UI.VSpacer(8)); // Abstand zur Tabelle
            
            // Mods-Tabelle
            if (items.length === 0) {
                catContainer.add(
                    new UI.Text("(keine Mods)").setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)", padding: "8px" })
                );
            } else {
                const modsTable = new UI.VDiv({ gap: 4 });
                modsTable.setStyle({
                    border: "1px solid var(--ui-color-border, rgba(0,0,0,0.1))",
                    borderRadius: "var(--ui-radius-sm)",
                    maxHeight: "250px",
                    overflowY: "auto"
                });
                
                for (const mod of items) {
                    const isBaseMod = baseModIds.has(mod.id);
                    const steamUrl = `https://steamcommunity.com/sharedfiles/filedetails/?id=${mod.id}`;
                    
                    const row = new UI.HDiv({ gap: 8, align: "center" }).setStyle({
                        padding: "6px 8px",
                        borderBottom: "1px solid var(--ui-color-border, rgba(0,0,0,0.05))",
                        fontSize: "0.85em",
                        background: ""
                    });
                    
                    // Checkbox: in Basis-Ansicht immer, sonst nur für Nicht-Basis-Mods
                    const showCheckbox = isBasisView || !isBaseMod;
                    if (showCheckbox) {
                        const checkbox = new UI.Checkbox(false, { label: "" });
                        checkbox.on("change", () => {
                            if (checkbox.getValue()) {
                                editState.modsToDelete.add(mod.id);
                            } else {
                                editState.modsToDelete.delete(mod.id);
                            }
                            row.setStyle({ 
                                background: checkbox.getValue() ? "var(--ui-color-error, rgba(255,0,0,0.08))" : "" 
                            });
                        });
                        row.add(checkbox);
                    } else {
                        // Placeholder (damit Spalten alignen)
                        row.add(new UI.Span("").setStyle({ minWidth: "20px" }));
                    }
                    
                    // Name
                    const nameSpan = new UI.Span(mod.name).setStyle({ flex: "1", textAlign: "left" });
                    row.add(nameSpan);
                    
                    // ID
                    const idSpan = new UI.Span(`(${mod.id})`).setStyle({ minWidth: "140px", textAlign: "right", color: "var(--ui-color-text-muted)", fontSize: "0.8em" });
                    row.add(idSpan);
                    
                    // Steam Link
                    const steamLink = new UI.Link("🔗", steamUrl, { 
                        target: "_blank",
                        title: "Steam Workshop öffnen"
                    }).setStyle({
                        textDecoration: "none",
                        cursor: "pointer",
                        fontSize: "0.9em"
                    });
                    row.add(steamLink);
                    
                    // Basis-Badge
                    if (isBaseMod) {
                        const badge = new UI.Span("(Basis)").setStyle({ 
                            fontSize: "0.75em", 
                            color: "var(--ui-color-text-muted)",
                            fontStyle: "italic",
                            marginRight: "4px"
                        });
                        row.add(badge);
                    }
                    
                    displayedIds.add(mod.id);
                    modsTable.add(row);
                }
                
                catContainer.add(modsTable);
            }
            
            container.add(catContainer);
        }
        
        // Extra-Sektion für Minus-Mods (Mods aus Basis entfernen) nur in Config-Ansicht (nicht Basis)
        if (!isBasisView) {
            const minusContainer = new UI.VDiv({ gap: 8 });
            minusContainer.setStyle({
                border: "2px solid var(--ui-color-error, #ff6b6b)",
                borderRadius: "var(--ui-radius-md)",
                padding: "12px",
                background: "var(--ui-color-surface)"
            });
            
            minusContainer.add(
                new UI.Heading("Minus-Mods (aus Basis entfernen)", { level: 5 }).setStyle({ margin: "0 0 8px 0", color: "var(--ui-color-error, #ff6b6b)" })
            );
            
            const minusText = new UI.Text("Diese Mods werden NICHT geladen (auch nicht aus der Basis):").setStyle({ fontSize: "0.85em", color: "var(--ui-color-text-muted)", marginBottom: "8px" });
            minusContainer.add(minusText);
            
            const minusInputRow = new UI.HDiv({ gap: 8, align: "stretch" });
            
            const addMinusBtn = new UI.Button("Add Minus").setStyle({
                padding: "8px 16px",
                fontSize: "0.85em",
                minWidth: "120px",
                whiteSpace: "nowrap",
                background: "var(--ui-color-error, #ff6b6b)"
            });
            
            const minusTextarea = new UI.TextArea("", { placeholder: "IDs oder Steam-Links (eine pro Zeile)", rows: 4 });
            minusTextarea.setStyle({ flex: "1", padding: "8px", fontFamily: "monospace", fontSize: "0.85em" });
            
            addMinusBtn.el.addEventListener("click", () => {
                const text = minusTextarea.el.value.trim();
                if (!text) {
                    alert("Bitte geben Sie mindestens eine Mod-ID ein");
                    return;
                }
                
                const lines = text.split("\n").map(l => l.trim()).filter(l => l.length > 0);
                let added = 0;
                for (const line of lines) {
                    const modId = _extractModId(line);
                    if (modId) {
                        editState.modsToAdd.push({ id: modId, name: `Minus ${modId}`, category: "minus_mods" });
                        added++;
                        console.log("Added minus mod:", modId);
                    }
                }
                
                minusTextarea.el.value = ""; // Clear
                alert(`${added} Minus-Mod(s) hinzugefügt`);
            });
            
            minusInputRow.add(addMinusBtn, minusTextarea);
            minusContainer.add(minusInputRow);
            
            container.add(minusContainer);
        }
        
        // Pending Mods Display - shows newly added mods
        const pendingModsContainer = new UI.VDiv({ gap: 8 });
        pendingModsContainer.setStyle({ display: "none", marginTop: "12px" });
        
        const updatePendingDisplay = () => {
            // Clear pending display
            pendingModsContainer.el.innerHTML = "";
            
            const pendingByCategory = {};
            for (const mod of editState.modsToAdd) {
                const cat = mod.category || "serverMods";
                if (!pendingByCategory[cat]) pendingByCategory[cat] = [];
                pendingByCategory[cat].push(mod);
            }
            
            if (Object.keys(pendingByCategory).length > 0) {
                pendingModsContainer.el.style.display = "block";
                
                pendingModsContainer.add(
                    new UI.Heading("⏳ Pending Mods (not yet saved)", { level: 5 }).setStyle({ 
                        margin: "0 0 8px 0", 
                        color: "var(--ui-color-warning, orange)" 
                    })
                );
                
                for (const [cat, mods] of Object.entries(pendingByCategory)) {
                    const catLabel = categoryLabels[cat] || cat;
                    const catDiv = new UI.VDiv({ gap: 4 });
                    catDiv.setStyle({
                        border: "1px solid var(--ui-color-border)",
                        borderRadius: "var(--ui-radius-sm)",
                        padding: "8px",
                        background: "var(--ui-color-surface)"
                    });
                    
                    catDiv.add(
                        new UI.Text(`${catLabel} (${mods.length})`).setStyle({ 
                            fontWeight: "bold", 
                            fontSize: "0.85em",
                            marginBottom: "4px"
                        })
                    );
                    
                    const modsList = new UI.VDiv({ gap: 2 });
                    for (const mod of mods) {
                        const row = new UI.HDiv({ gap: 8, align: "center" }).setStyle({
                            padding: "4px 6px",
                            borderBottom: "1px solid var(--ui-color-border, rgba(0,0,0,0.05))",
                            fontSize: "0.8em"
                        });
                        
                        const nameSpan = new UI.Span(mod.name).setStyle({ flex: "1" });
                        const idSpan = new UI.Span(`(${mod.id})`).setStyle({ 
                            color: "var(--ui-color-text-muted)", 
                            fontSize: "0.9em" 
                        });
                        
                        // Remove button
                        const removeBtn = new UI.Button("×").setStyle({
                            padding: "2px 6px",
                            fontSize: "0.9em",
                            background: "var(--ui-color-error, #ff6b6b)",
                            color: "white",
                            cursor: "pointer",
                            minWidth: "24px"
                        });
                        removeBtn.el.title = "Aus Pending entfernen";
                        removeBtn.el.addEventListener("click", () => {
                            editState.modsToAdd = editState.modsToAdd.filter(m => 
                                !(String(m.id) === String(mod.id) && m.category === cat)
                            );
                            updatePendingDisplay();
                        });
                        
                        row.add(nameSpan, idSpan, removeBtn);
                        modsList.add(row);
                    }
                    
                    catDiv.add(modsList);
                    pendingModsContainer.add(catDiv);
                }
            } else {
                pendingModsContainer.el.style.display = "none";
            }
            
            updateSummary();
        };
        
        // Summary
        const summary = new UI.Text("");
        const updateSummary = () => {
            const deleteCount = editState.modsToDelete.size;
            const addCount = editState.modsToAdd.length;
            summary.setText(
                `Änderungen: ${deleteCount > 0 ? deleteCount + " zum Löschen" : ""}${deleteCount > 0 && addCount > 0 ? ", " : ""}${addCount > 0 ? addCount + " zum Hinzufügen" : ""}${deleteCount === 0 && addCount === 0 ? "Keine Änderungen" : ""}`
            );
            summary.setStyle({ marginTop: "12px", padding: "8px 12px", fontSize: "0.9em", color: "var(--ui-color-text-muted)", background: "var(--ui-color-surface)", borderRadius: "var(--ui-radius-sm)" });
        };
        
        const checkSummary = setInterval(updateSummary, 500);
        updateSummary();
        container.add(pendingModsContainer, summary);
        
        return container;
    }
    
    // Helper: Extract mod ID from Steam URL or direct ID
    function _extractModId(input) {
        // Check if it's a Steam URL
        const urlMatch = input.match(/id=(\d+)/);
        if (urlMatch) {
            return urlMatch[1];
        }
        
        // Check if it's just a number (mod ID)
        if (/^\d+$/.test(input)) {
            return input;
        }
        
        return null;
    }
    
    
    // Load Basis Mods für Bearbeitung
    async function loadBaseMods() {
        try {
            const resp = await apiClient.getDefaults();
            if (!resp.ok) throw new Error(resp.detail || "Failed to load defaults");
            
            selectedConfigName = "BASE_MODS_VIEW";
            _markSelected("BASE_MODS_VIEW");
            // Set configData for _buildEditModsSection to detect isBasisView correctly
            configData = resp;
            
            // Clear all tabs
            while (basisContent.el.firstChild) basisContent.el.firstChild.remove();
            while (overridesContent.el.firstChild) overridesContent.el.firstChild.remove();
            while (previewContent.el.firstChild) previewContent.el.firstChild.remove();
            while (editContent.el.firstChild) editContent.el.firstChild.remove();
            
            // Nur Edit-Tab zeigen
            basisContent.add(new UI.Text("---"));
            overridesContent.add(new UI.Text("---"));
            previewContent.add(new UI.Text("---"));
            
            editContent.add(
                new UI.Heading("Basis Mods bearbeiten", { level: 4 }).setStyle({ margin: "0 0 12px 0" }),
                new UI.Text("Hier können Sie die Standard-Mods für alle Konfigurationen einstellen.").setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)", marginBottom: "12px" }),
                _buildEditModsSection(resp.defaults.mods)
            );
        } catch (err) {
            console.error("Failed to load base mods:", err);
            while (editContent.el.firstChild) editContent.el.firstChild.remove();
            editContent.add(new UI.Text(`Fehler: ${err.message}`).setStyle({ color: "red" }));
        }
    }

    // Load variant (similar to loadConfigDetail but for variants)
    async function loadVariant(variantName, { manual = false, silent = false } = {}) {
        try {
            selectedConfigName = `variant:${variantName}`;
            const resp = await apiClient.getVariant(variantName);
            if (!resp.ok) throw new Error(resp.detail || "Failed to load variant");
            
            configData = resp;
            _markSelected(`variant:${variantName}`);
            
            // Clear and rebuild Basis tab (shows base mods)
            while (basisContent.el.firstChild) basisContent.el.firstChild.remove();
            basisContent.add(
                new UI.Heading("Basis Mods", { level: 4 }).setStyle({ margin: "0" }),
                new UI.Text("Diese Mods werden von allen Varianten als Basis verwendet.").setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)" }),
                _buildModsTable("Basis Mods", resp.data.base)
            );
            
            // Clear and rebuild Overrides tab (shows variant overrides: added/removed/replace)
            while (overridesContent.el.firstChild) overridesContent.el.firstChild.remove();
            overridesContent.add(
                new UI.Heading(`Variante "${variantName}" - Overrides`, { level: 4 }).setStyle({ margin: "0" }),
                new UI.Text("Änderungen gegen die Basis-Mods.").setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)" }),
                _buildVariantOverrideView(resp.data.override)
            );
            
            // Clear and rebuild Merged tab (shows merged result)
            while (previewContent.el.firstChild) previewContent.el.firstChild.remove();
            previewContent.add(
                new UI.Heading("Merged Preview", { level: 4 }).setStyle({ margin: "0" }),
                new UI.Text("Resultierende Mods nach Anwendung der Overrides.").setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)" }),
                _buildModsTable("Merged Mods", resp.data.merged)
            );
            
            // Clear and rebuild Edit tab
            while (editContent.el.firstChild) editContent.el.firstChild.remove();
            editContent.add(
                new UI.Heading(`Edit Variante "${variantName}"`, { level: 4 }).setStyle({ margin: "0" }),
                new UI.Text("Editor für Varianten-Overrides (in Entwicklung)").setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)" })
            );
            
            return true;
        } catch (err) {
            if (!silent) {
                console.error("Failed to load variant:", err);
                while (basisContent.el.firstChild) basisContent.el.firstChild.remove();
                basisContent.add(new UI.Text(`Fehler: ${err.message}`).setStyle({ color: "red" }));
            }
            return false;
        }
    }

    // Save Basis Mods
    async function saveBaseMods() {
        try {
            // All fields expected by FileConfig_Mods
            const allCategories = ["serverMods", "baseMods", "clientMods", "maps", "missionMods", 
                                   "extraServer", "extraBase", "extraClient", "extraMaps", "extraMission", "minus_mods"];
            const modsPayload = {};
            
            // Start with existing defaults.mods from configData
            if (configData && configData.defaults && configData.defaults.mods) {
                for (const cat of allCategories) {
                    modsPayload[cat] = Array.isArray(configData.defaults.mods[cat]) 
                        ? [...configData.defaults.mods[cat]] 
                        : [];
                }
            } else {
                for (const cat of allCategories) modsPayload[cat] = [];
            }
            
            // Apply deletions -> remove from each category
            for (const id of editState.modsToDelete) {
                const asNum = Number(id);
                for (const cat of allCategories) {
                    modsPayload[cat] = modsPayload[cat].filter(m => Number(m.id) !== asNum);
                }
            }
            
            // Apply additions -> add to respective category
            for (const add of editState.modsToAdd || []) {
                const cat = add.category || "serverMods";
                if (!Array.isArray(modsPayload[cat])) modsPayload[cat] = [];
                const asNum = Number(add.id);
                if (!modsPayload[cat].some(m => Number(m.id) === asNum)) {
                    modsPayload[cat].push({ id: asNum, name: add.name || `Mod ${asNum}` });
                }
            }
            
            console.log("Saving defaults payload:", { mods: modsPayload });
            
            const resp = await apiClient.saveDefaults({ mods: modsPayload });
            if (!resp.ok) throw new Error(resp.detail || "Failed to save defaults");
            
            alert("Basis-Mods gespeichert!");
            await loadBaseMods(); // Refresh
        } catch (err) {
            console.error("Failed to save base mods:", err);
            if (err.data && err.data.detail) {
                console.error("Validation errors:", JSON.stringify(err.data.detail, null, 2));
            }
            alert(`Fehler beim Speichern: ${err.message}`);
        }
    }
    
    // Save button handler
    saveBtn.el.addEventListener("click", async () => {
        if (!selectedConfigName) {
            alert("Bitte wählen Sie eine Konfiguration aus");
            return;
        }

        // Handle saving BASE_MODS_VIEW separately
        if (selectedConfigName === "BASE_MODS_VIEW") {
            await saveBaseMods();
            return;
        }

        try {
            // Build a proper override payload expected by the server (FileConfig_Override)
            // Start from existing overrides (if any) to preserve other fields
            const overridePayload = JSON.parse(JSON.stringify(configData.overrides || {}));

            // DLC mapping: UI uses display names, server expects a boolean object
            const normalizeDlcName = (name) => String(name ?? "")
                .toLowerCase()
                .replace(/\./g, "")
                .replace(/\s+/g, " ")
                .trim();

            const dlcNameToKey = {
                "contact": "contact",
                "csla iron curtain": "csla_iron_curtain",
                "global mobilization": "global_mobilization",
                "sog prairie fire": "sog_prairie_fire",
                "western sahara": "western_sahara",
                "spearhead 1944": "spearhead_1944",
                "reaction forces": "reaction_forces",
                "expeditionary forces": "expeditionary_forces",
            };

            const dlcFields = {
                contact: false,
                csla_iron_curtain: false,
                global_mobilization: false,
                sog_prairie_fire: false,
                western_sahara: false,
                spearhead_1944: false,
                reaction_forces: false,
                expeditionary_forces: false,
            };

            if (editState.selectedDlc) {
                const key = dlcNameToKey[normalizeDlcName(editState.selectedDlc)];
                if (key) dlcFields[key] = true;
            }

            overridePayload.dlcs = dlcFields;

            // Mods: merge edits (modsToAdd / modsToDelete) into existing override.mods
            const modCategories = ["serverMods", "baseMods", "clientMods", "maps", "missionMods", "extraServer", "extraBase", "extraClient", "extraMaps", "extraMission", "minus_mods"];
            const existingMods = overridePayload.mods || {};
            for (const c of modCategories) {
                if (!Array.isArray(existingMods[c])) existingMods[c] = [];
            }

            // Apply deletions -> add to minus_mods
            for (const id of editState.modsToDelete) {
                const asNum = Number(id);
                if (!existingMods.minus_mods.some(m => Number(m.id) === asNum)) {
                    existingMods.minus_mods.push({ id: asNum, name: `Minus ${asNum}` });
                }
            }

            // Apply additions -> push to respective category
            for (const add of editState.modsToAdd || []) {
                const cat = add.category || "serverMods";
                if (!Array.isArray(existingMods[cat])) existingMods[cat] = [];
                const asNum = Number(add.id);
                if (!existingMods[cat].some(m => Number(m.id) === asNum)) {
                    existingMods[cat].push({ id: asNum, name: add.name || `Mod ${asNum}` });
                }
            }

            overridePayload.mods = existingMods;

            console.log("Saving override payload:", overridePayload);

            const resp = await apiClient.saveConfig(selectedConfigName, overridePayload);
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

import * as UI from "/ui-kit-0/src/ui-kit-0.js";
import { apiClient } from "./api/client.js";

export function createMissionsContent() {
    const container = new UI.VDiv({ gap: 16 });
    
    // State
    let selectedConfig = null;
    let selectedMission = null;
    let allConfigs = [];
    let missions = [];
    let updateItems = [];
    let updateSelection = new Set();
    
    // ===== Header =====
    container.add(
        new UI.Heading("Missionen", { level: 2 }).setStyle({ margin: "0 0 16px 0" })
    );
    
    // ===== Config Selection Section =====
    const configSection = new UI.VDiv({ gap: 12 });
    configSection.setStyle({
        background: "var(--ui-color-surface)",
        border: "1px solid var(--ui-color-border)",
        borderRadius: "var(--ui-radius-md)",
        padding: "16px"
    });
    
    configSection.add(
        new UI.Heading("1. Konfiguration auswählen", { level: 4 }).setStyle({ margin: "0 0 8px 0" })
    );
    
    const configSelect = new UI.Select({ options: [], value: "" });
    configSelect.setStyle({ minWidth: "300px" });
    
    configSelect.on("change", async () => {
        selectedConfig = configSelect.getValue();
        selectedMission = null;
        missionList.el.innerHTML = "";
        detailsSection.setStyle({ display: "none" });
        updateItems = [];
        updateSelection = new Set();
        updateSummary.setText("Keine Prüfung durchgeführt.");
        updatesList.el.innerHTML = "";
        updateBtn.setDisabled(true);
        setUpdateProgress({ mode: "hidden" });
        
        if (selectedConfig) {
            await loadMissionsForConfig(selectedConfig);
            missionSection.setStyle({ display: "block" });
            updateSection.setStyle({ display: "block" });
        } else {
            missionSection.setStyle({ display: "none" });
            updateSection.setStyle({ display: "none" });
        }
    });
    
    configSection.add(configSelect);
    container.add(configSection);

    // ===== Mod Updates Section =====
    const updateSection = new UI.VDiv({ gap: 12 });
    updateSection.setStyle({
        background: "var(--ui-color-surface)",
        border: "1px solid var(--ui-color-border)",
        borderRadius: "var(--ui-radius-md)",
        padding: "16px",
        display: "none"
    });

    updateSection.add(
        new UI.Heading("2. Mod-Updates", { level: 4 }).setStyle({ margin: "0 0 8px 0" })
    );

    const updateActions = new UI.HDiv({ gap: 8, align: "center" });
    const checkUpdatesBtn = new UI.Button("🔍 Aktualität prüfen", { variant: "secondary" });
    const selectAllBtn = new UI.Button("Alle auswählen", { variant: "secondary" });
    const selectNoneBtn = new UI.Button("Keine auswählen", { variant: "secondary" });
    const updateBtn = new UI.Button("⬇️ Update starten");
    updateBtn.setDisabled(true);

    updateActions.add(checkUpdatesBtn, selectAllBtn, selectNoneBtn, updateBtn);

    const updateSummary = new UI.Text("Keine Prüfung durchgeführt.");
    updateSummary.setStyle({ fontSize: "0.85em", color: "var(--ui-color-text-muted)" });

    const updateProgressWrap = new UI.HDiv({ gap: 8, align: "center" });
    updateProgressWrap.setStyle({ display: "none" });
    const updateProgressBar = new UI.BaseElement("progress");
    updateProgressBar.setAttr("max", "100");
    updateProgressBar.setStyle({ width: "240px", height: "10px" });
    const updateProgressText = new UI.Span("").setStyle({
        fontSize: "0.8em",
        color: "var(--ui-color-text-muted)"
    });
    updateProgressWrap.add(updateProgressBar, updateProgressText);

    const updatesList = new UI.VDiv({ gap: 6 });
    updatesList.setStyle({ maxHeight: "340px", overflowY: "auto" });

    updateSection.add(updateActions, updateSummary, updateProgressWrap, updatesList);
    container.add(updateSection);
    
    // ===== Missions Section =====
    const missionSection = new UI.VDiv({ gap: 12 });
    missionSection.setStyle({
        background: "var(--ui-color-surface)",
        border: "1px solid var(--ui-color-border)",
        borderRadius: "var(--ui-radius-md)",
        padding: "16px",
        display: "none"
    });
    
    missionSection.add(
        new UI.Heading("3. Mission auswählen", { level: 4 }).setStyle({ margin: "0 0 12px 0" })
    );
    
    const missionList = new UI.VDiv({ gap: 8 });
    missionList.setStyle({
        maxHeight: "400px",
        overflowY: "auto"
    });
    
    missionSection.add(missionList);
    container.add(missionSection);
    
    // ===== Mission Details Section =====
    const detailsSection = new UI.VDiv({ gap: 12 });
    detailsSection.setStyle({
        background: "var(--ui-color-surface)",
        border: "2px solid var(--ui-color-nav-active)",
        borderRadius: "var(--ui-radius-md)",
        padding: "16px",
        display: "none"
    });
    
    const missionTitle = new UI.Heading("", { level: 4 }).setStyle({ margin: "0 0 8px 0" });
    const missionDesc = new UI.Text("");
    const requiredModsList = new UI.VDiv({ gap: 4 });
    const uploadArea = new UI.VDiv({ gap: 8 });
    
    const startBtn = new UI.Button("✓ Starten").setStyle({ 
        padding: "10px 20px", 
        background: "var(--ui-color-success, #4CAF50)",
        color: "white",
        cursor: "pointer"
    });
    
    const cancelBtn = new UI.Button("Abbrechen").setStyle({ 
        padding: "10px 20px",
        background: "var(--ui-color-surface)",
        cursor: "pointer"
    });
    
    cancelBtn.el.addEventListener("click", () => {
        selectedMission = null;
        detailsSection.setStyle({ display: "none" });
        displayMissionsList();
    });
    
    startBtn.el.addEventListener("click", () => {
        alert(`Würde starten:\nConfig: ${selectedConfig}\nMission: ${selectedMission}`);
    });
    
    detailsSection.add(
        missionTitle,
        missionDesc,
        new UI.Heading("Benötigte Mods", { level: 5 }).setStyle({ margin: "8px 0 4px 0" }),
        requiredModsList,
        new UI.Heading("Custom Mods", { level: 5 }).setStyle({ margin: "16px 0 8px 0" }),
        uploadArea,
        new UI.HDiv({ gap: 8, align: "center" }).add(startBtn, cancelBtn)
    );
    
    container.add(detailsSection);
    
    // ===== API Integration =====
    
    async function loadConfigs() {
        try {
            const resp = await apiClient.getConfigs();
            if (!resp.ok) throw new Error(resp.detail);
            
            allConfigs = resp.configs;
            const options = [{ label: "-- Wähle eine Konfiguration --", value: "" }];
            for (const cfg of resp.configs) {
                options.push({
                    label: `${cfg.name} (${cfg.hostname}:${cfg.port})`,
                    value: cfg.name
                });
            }
            
            configSelect.setOptions(options);
        } catch (err) {
            console.error("Failed to load configs:", err);
            configSelect.setOptions([
                { label: `❌ Fehler: ${err.message}`, value: "" }
            ]);
        }
    }
    
    async function loadMissionsForConfig(configName) {
        try {
            const resp = await apiClient.getMissions(configName);
            if (!resp.ok) throw new Error(resp.detail || "Failed to load missions");
            missions = Array.isArray(resp.missions) ? resp.missions : [];
            
            displayMissionsList();
        } catch (err) {
            console.error("Failed to load missions:", err);
            missionList.el.innerHTML = "";
            missionList.add(
                new UI.Text(`❌ Fehler beim Laden der Missionen: ${err.message}`)
                    .setStyle({ color: "var(--ui-color-error)" })
            );
        }
    }

    function formatEpoch(ts) {
        if (!ts) return "—";
        try {
            return new Date(ts * 1000).toLocaleString();
        } catch {
            return "—";
        }
    }

    function needsUpdate(item) {
        return !item.installed || item.status !== "up_to_date";
    }

    function updatePriority(item) {
        if (!item.installed) return 0;
        if (item.status === "outdated") return 1;
        if (item.status !== "up_to_date") return 2;
        return 3;
    }

    function setUpdateProgress({ mode = "hidden", value = 0, max = 100, text = "" } = {}) {
        if (mode === "hidden") {
            updateProgressWrap.setStyle({ display: "none" });
            updateProgressText.setText("");
            updateProgressBar.removeAttr("value");
            return;
        }
        updateProgressWrap.setStyle({ display: "flex" });
        updateProgressText.setText(text || "");
        if (mode === "indeterminate") {
            updateProgressBar.removeAttr("value");
            updateProgressBar.setAttr("max", String(max));
        } else {
            updateProgressBar.setAttr("max", String(max));
            updateProgressBar.setAttr("value", String(value));
        }
    }

    function renderUpdateList() {
        updatesList.el.innerHTML = "";

        if (!Array.isArray(updateItems) || updateItems.length === 0) {
            updatesList.add(
                new UI.Text("Keine Mods gefunden.").setStyle({
                    color: "var(--ui-color-text-muted)",
                    fontStyle: "italic"
                })
            );
            updateBtn.setDisabled(true);
            return;
        }

        let outdated = 0;
        let unknown = 0;
        let upToDate = 0;
        let missing = 0;

        updateItems.forEach(item => {
            if (!item.installed) missing += 1;
            if (item.status === "outdated") outdated += 1;
            else if (item.status === "up_to_date") upToDate += 1;
            else unknown += 1;
        });

        updateSummary.setText(`Gefunden: ${updateItems.length} • Fehlend: ${missing} • Veraltet: ${outdated} • Unbekannt: ${unknown} • Aktuell: ${upToDate}`);
        updateBtn.setDisabled(updateSelection.size === 0);

        const sortedItems = [...updateItems].sort((a, b) => {
            const pa = updatePriority(a);
            const pb = updatePriority(b);
            if (pa !== pb) return pa - pb;
            const an = (a.name || "").toLowerCase();
            const bn = (b.name || "").toLowerCase();
            if (an !== bn) return an.localeCompare(bn);
            return (a.id || 0) - (b.id || 0);
        });

        sortedItems.forEach(item => {
            const key = `${item.kind}:${item.id}`;
            const checkbox = new UI.Checkbox(updateSelection.has(key), { label: item.name || `Mod ${item.id}` });
            checkbox.on("change", () => {
                if (checkbox.getValue()) {
                    updateSelection.add(key);
                } else {
                    updateSelection.delete(key);
                }
                updateBtn.setDisabled(updateSelection.size === 0);
            });

            let statusText = "❓ unbekannt";
            let statusColor = "var(--ui-color-text-muted)";
            if (!item.installed) {
                statusText = "❌ fehlt";
                statusColor = "var(--ui-color-error)";
            } else if (item.status === "up_to_date") {
                statusText = "✅ aktuell";
                statusColor = "var(--ui-color-success, #4CAF50)";
            } else if (item.status === "outdated") {
                statusText = "⬇️ Update";
                statusColor = "var(--ui-color-warning, #FF9800)";
            }

            const row = new UI.HDiv({ gap: 8, align: "center" }).setStyle({
                padding: "6px 8px",
                borderBottom: "1px solid var(--ui-color-border)",
                fontSize: "0.85em"
            });

            const idSpan = new UI.Span(`(${item.id})`).setStyle({
                minWidth: "110px",
                textAlign: "right",
                color: "var(--ui-color-text-muted)"
            });

            const kindSpan = new UI.Span(item.kind).setStyle({
                minWidth: "90px",
                fontSize: "0.8em",
                color: "var(--ui-color-text-muted)"
            });

            const statusSpan = new UI.Span(statusText).setStyle({
                minWidth: "90px",
                color: statusColor,
                fontWeight: "600"
            });

            const timeText = item.installed
                ? `Local: ${formatEpoch(item.localTimestamp)} | Remote: ${formatEpoch(item.remoteTimestamp)}`
                : "Nicht installiert";

            const timeSpan = new UI.Span(timeText).setStyle({
                fontSize: "0.8em",
                color: "var(--ui-color-text-muted)"
            });

            row.add(checkbox, idSpan, kindSpan, statusSpan, timeSpan);
            updatesList.add(row);
        });
    }

    async function checkModUpdates() {
        if (!selectedConfig) return;
        checkUpdatesBtn.setDisabled(true);
        updateBtn.setDisabled(true);
        updateSummary.setText("Prüfe Aktualität...");
        updatesList.el.innerHTML = "";
        setUpdateProgress({ mode: "indeterminate", text: "Prüfe Mods…" });

        try {
            const resp = await apiClient.getWorkshopUpdates(selectedConfig);
            if (!resp.ok) throw new Error(resp.detail || "Update-Check fehlgeschlagen");
            updateItems = Array.isArray(resp.items) ? resp.items : [];
            updateSelection = new Set(
                updateItems
                    .filter(item => needsUpdate(item))
                    .map(item => `${item.kind}:${item.id}`)
            );
            renderUpdateList();
        } catch (err) {
            console.error("Failed to check mod updates:", err);
            updateSummary.setText(`❌ Fehler beim Prüfen: ${err.message}`);
            updatesList.el.innerHTML = "";
            updateBtn.setDisabled(true);
        } finally {
            setUpdateProgress({ mode: "hidden" });
            checkUpdatesBtn.setDisabled(false);
        }
    }

    async function runModUpdates() {
        if (!selectedConfig || updateSelection.size === 0) return;
        const items = updateItems
            .filter(item => updateSelection.has(`${item.kind}:${item.id}`))
            .map(item => ({ id: item.id, kind: item.kind, name: item.name }));

        if (items.length === 0) return;

        updateBtn.setDisabled(true);
        checkUpdatesBtn.setDisabled(true);

        const total = items.length;
        let done = 0;
        const updated = [];
        const skipped = [];
        const failed = [];

        updateSummary.setText(`Update läuft... (${items.length} Mods)`);
        setUpdateProgress({ mode: "determinate", value: 0, max: total, text: `Update startet (0/${total})` });

        try {
            for (const item of items) {
                const label = item.name || `Mod ${item.id}`;
                setUpdateProgress({
                    mode: "determinate",
                    value: done,
                    max: total,
                    text: `Update: ${label} (${done}/${total})`
                });

                try {
                    const resp = await apiClient.updateWorkshopItems(selectedConfig, [{ id: item.id, kind: item.kind }]);
                    if (!resp.ok) throw new Error(resp.detail || "Update fehlgeschlagen");
                    const data = resp.data || {};
                    if (Array.isArray(data.updated)) updated.push(...data.updated);
                    if (Array.isArray(data.skipped)) skipped.push(...data.skipped);
                    if (Array.isArray(data.failed)) failed.push(...data.failed);
                } catch (err) {
                    failed.push({ id: item.id, kind: item.kind, error: err.message });
                }

                done += 1;
                setUpdateProgress({
                    mode: "determinate",
                    value: done,
                    max: total,
                    text: `Update läuft… (${done}/${total})`
                });
            }

            const detail = `Updated ${updated.length} • Skipped ${skipped.length} • Failed ${failed.length}`;
            updateSummary.setText(failed.length ? `⚠️ ${detail}` : detail);
            await checkModUpdates();
        } catch (err) {
            console.error("Failed to update mods:", err);
            updateSummary.setText(`❌ Update fehlgeschlagen: ${err.message}`);
        } finally {
            setUpdateProgress({ mode: "hidden" });
            checkUpdatesBtn.setDisabled(false);
            updateBtn.setDisabled(updateSelection.size === 0);
        }
    }

    checkUpdatesBtn.onClick(() => {
        checkModUpdates();
    });

    selectAllBtn.onClick(() => {
        updateSelection = new Set(
            updateItems
                .filter(item => needsUpdate(item))
                .map(item => `${item.kind}:${item.id}`)
        );
        renderUpdateList();
    });

    selectNoneBtn.onClick(() => {
        updateSelection = new Set();
        renderUpdateList();
    });

    updateBtn.onClick(() => {
        runModUpdates();
    });
    
    function displayMissionsList() {
        missionList.el.innerHTML = "";
        
        if (missions.length === 0) {
            missionList.add(
                new UI.Text("Keine Missionen verfügbar").setStyle({ 
                    color: "var(--ui-color-text-muted)", 
                    fontStyle: "italic" 
                })
            );
            return;
        }
        
        missions.forEach(mission => {
            const requiredMods = Array.isArray(mission.requiredMods) ? mission.requiredMods : [];
            const optionalMods = Array.isArray(mission.optionalMods) ? mission.optionalMods : [];
            const configMods = allConfigs.find(c => c.name === selectedConfig)?.workshop?.mods || [];
            const compatible = requiredMods.every(m => configMods.some(c => c.id === m.id));
            const hashMismatch = mission.configHashMatch === false;
            
            const missionCard = new UI.HDiv({ gap: 12, align: "center" });
            missionCard.setStyle({
                border: `2px solid ${compatible ? "var(--ui-color-success, #4CAF50)" : "var(--ui-color-warning, #FF9800)"}`,
                borderRadius: "var(--ui-radius-md)",
                padding: "12px",
                cursor: "pointer",
                background: selectedMission === mission.name ? "var(--ui-color-nav-active)" : "var(--ui-color-bg)",
                transition: "all 0.2s"
            });
            
            // Status icon
            const statusIcon = compatible 
                ? new UI.Span("✓")
                    .setStyle({ fontSize: "1.2em", color: "var(--ui-color-success, #4CAF50)", minWidth: "20px" })
                : new UI.Span("⚠")
                    .setStyle({ fontSize: "1.2em", color: "var(--ui-color-warning, #FF9800)", minWidth: "20px" });
            
            // Mission info
            const infoDiv = new UI.VDiv({ gap: 2 }).setStyle({ flex: "1" });
            infoDiv.add(
                new UI.Heading(mission.name, { level: 5 }).setStyle({ margin: "0" }),
                new UI.Text(mission.description || "(keine Beschreibung)").setStyle({ 
                    fontSize: "0.85em", 
                    color: "var(--ui-color-text-muted)" 
                }),
                new UI.Text(`${requiredMods.length} benötigte Mods${optionalMods.length ? `, ${optionalMods.length} optional` : ""}`).setStyle({ 
                    fontSize: "0.8em", 
                    color: compatible 
                        ? "var(--ui-color-text-muted)" 
                        : "var(--ui-color-warning, #FF9800)",
                    fontWeight: compatible ? "normal" : "bold"
                })
            );
            if (hashMismatch) {
                infoDiv.add(
                    new UI.Text("⚠️ Config wurde seit Upload geändert").setStyle({
                        fontSize: "0.8em",
                        color: "var(--ui-color-warning, #FF9800)",
                        fontWeight: "bold"
                    })
                );
            }
            
            missionCard.add(statusIcon, infoDiv);
            
            missionCard.el.addEventListener("click", () => {
                selectedMission = mission.name;
                displayMissionsList();
                displayMissionDetails(mission);
                detailsSection.setStyle({ display: "block" });
            });
            
            missionList.add(missionCard);
        });
    }
    
    function displayMissionDetails(mission) {
        missionTitle.setText(mission.name);
        missionDesc.setText(mission.description || "(keine Beschreibung)");

        const requiredMods = Array.isArray(mission.requiredMods) ? mission.requiredMods : [];
        const optionalMods = Array.isArray(mission.optionalMods) ? mission.optionalMods : [];
        
        // Required mods list
        requiredModsList.el.innerHTML = "";
        if (requiredMods.length === 0) {
            requiredModsList.add(
                new UI.Text("Keine speziellen Anforderungen").setStyle({ 
                    color: "var(--ui-color-text-muted)" 
                })
            );
        } else {
            const modsList = new UI.VDiv({ gap: 3 });
            const configMods = allConfigs.find(c => c.name === selectedConfig)?.workshop?.mods || [];
            
            requiredMods.forEach(mod => {
                const isMissing = !configMods.some(m => m.id === mod.id);
                
                const modRow = new UI.HDiv({ gap: 8, align: "center" }).setStyle({
                    padding: "6px 8px",
                    borderBottom: "1px solid var(--ui-color-border)",
                    fontSize: "0.9em"
                });
                
                modRow.add(
                    new UI.Span(isMissing ? "❌" : "✓").setStyle({ 
                        minWidth: "20px",
                        color: isMissing ? "var(--ui-color-error)" : "var(--ui-color-success, #4CAF50)"
                    }),
                    new UI.Span(mod.name).setStyle({ flex: "1" }),
                    new UI.Span(`(${mod.id})`).setStyle({ 
                        fontSize: "0.8em", 
                        color: "var(--ui-color-text-muted)" 
                    })
                );
                modsList.add(modRow);
            });
            requiredModsList.add(modsList);
        }

        if (optionalMods.length > 0) {
            const optionalTitle = new UI.Text("Optionale Mods:").setStyle({
                marginTop: "8px",
                fontSize: "0.85em",
                fontWeight: "600"
            });
            const optionalList = new UI.VDiv({ gap: 2 });
            optionalMods.forEach(mod => {
                optionalList.add(
                    new UI.Text(`• ${mod.name || "Mod"} (${mod.id})`).setStyle({
                        fontSize: "0.85em",
                        color: "var(--ui-color-text-muted)"
                    })
                );
            });
            requiredModsList.add(optionalTitle, optionalList);
        }

        if (mission.configHashMatch === false) {
            requiredModsList.add(
                new UI.Text("⚠️ Die zugewiesene Konfiguration wurde seit Upload geändert.")
                    .setStyle({ fontSize: "0.85em", color: "var(--ui-color-warning, #FF9800)", fontWeight: "bold" })
            );
        }
        
        // Upload area
        uploadArea.el.innerHTML = "";
        const uploadContainer = new UI.VDiv({ gap: 8 });
        uploadContainer.setStyle({
            border: "2px dashed var(--ui-color-border)",
            borderRadius: "var(--ui-radius-md)",
            padding: "16px",
            textAlign: "center",
            cursor: "pointer",
            transition: "all 0.2s"
        });
        
        uploadContainer.add(
            new UI.Text("📤 Custom Mods hierher ziehen oder klicken").setStyle({
                fontWeight: "600",
                fontSize: "0.95em"
            }),
            new UI.Text(`(für ${mission.name} + ${selectedConfig})`).setStyle({
                fontSize: "0.85em",
                color: "var(--ui-color-text-muted)"
            })
        );
        
        uploadContainer.el.addEventListener("click", () => {
            alert(`Upload würde starten:\nConfig: ${selectedConfig}\nMission: ${mission.name}`);
        });
        
        uploadContainer.el.addEventListener("dragover", (e) => {
            e.preventDefault();
            uploadContainer.setStyle({ background: "rgba(var(--ui-color-nav-active), 0.1)" });
        });
        
        uploadContainer.el.addEventListener("dragleave", () => {
            uploadContainer.setStyle({ background: "" });
        });
        
        uploadArea.add(uploadContainer);
    }
    
    // Initial load
    loadConfigs();
    
    return container;
}

import * as UI from "/ui-kit-0/src/ui-kit-0.js";
import { apiClient } from "./api/client.js";

export function createMissionsContent() {
    const container = new UI.VDiv({ gap: 16 });
    
    // State
    let selectedConfig = null;
    let selectedMission = null;
    let selectedMissionData = null;
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
        selectedMissionData = null;
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
            uploadSection.setStyle({ display: "block" });
            updateSection.setStyle({ display: "block" });
        } else {
            missionSection.setStyle({ display: "none" });
            uploadSection.setStyle({ display: "none" });
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

    // ===== Mission Upload Section =====
    const uploadSection = new UI.VDiv({ gap: 12 });
    uploadSection.setStyle({
        background: "var(--ui-color-surface)",
        border: "1px solid var(--ui-color-border)",
        borderRadius: "var(--ui-radius-md)",
        padding: "16px",
        display: "none"
    });

    uploadSection.add(
        new UI.Heading("3. Mission hochladen", { level: 4 }).setStyle({ margin: "0 0 8px 0" })
    );

    const uploadHelp = new UI.Text("Lade eine .pbo Mission hoch und verknüpfe sie mit der ausgewählten Konfiguration.");
    uploadHelp.setStyle({ fontSize: "0.85em", color: "var(--ui-color-text-muted)" });

    const uploadFileRow = new UI.HDiv({ gap: 8, align: "stretch" });
    const missionFileInput = document.createElement("input");
    missionFileInput.type = "file";
    missionFileInput.accept = ".pbo,.zip";
    missionFileInput.style.flex = "1";
    missionFileInput.style.padding = "8px";

    const uploadBtn = new UI.Button("📤 Mission hochladen");
    uploadBtn.setStyle({ padding: "8px 16px" });

    uploadFileRow.add(missionFileInput, uploadBtn);

    const uploadMetaRow = new UI.HDiv({ gap: 8, align: "stretch" });
    const missionNameInput = document.createElement("input");
    missionNameInput.type = "text";
    missionNameInput.placeholder = "Mission name (optional)";
    missionNameInput.style.flex = "1";
    missionNameInput.style.padding = "8px";

    const missionDescInput = new UI.TextArea("", { placeholder: "Beschreibung (optional)", rows: 2 });
    missionDescInput.setStyle({ flex: "2" });

    uploadMetaRow.add(missionNameInput, missionDescInput);

    const uploadStatus = new UI.Text("");
    uploadStatus.setStyle({ fontSize: "0.85em", color: "var(--ui-color-text-muted)" });

    uploadSection.add(uploadHelp, uploadMetaRow, uploadFileRow, uploadStatus);
    container.add(uploadSection);
    
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
    const missionFileInfo = new UI.Text("").setStyle({ fontSize: "0.85em", color: "var(--ui-color-text-muted)" });
    const missionUploadedInfo = new UI.Text("").setStyle({ fontSize: "0.85em", color: "var(--ui-color-text-muted)" });
    const requiredModsList = new UI.VDiv({ gap: 4 });
    const metaEditor = new UI.VDiv({ gap: 8 });

    const metaDescInput = new UI.TextArea("", { placeholder: "Beschreibung (optional)", rows: 3 });
    metaDescInput.setStyle({ width: "100%" });
    const saveMetaBtn = new UI.Button("💾 Metadaten speichern");
    const saveMetaStatus = new UI.Text("").setStyle({ fontSize: "0.85em", color: "var(--ui-color-text-muted)" });
    
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
        missionFileInfo,
        missionUploadedInfo,
        new UI.Heading("Benötigte Mods", { level: 5 }).setStyle({ margin: "8px 0 4px 0" }),
        requiredModsList,
        new UI.Heading("Metadaten bearbeiten", { level: 5 }).setStyle({ margin: "16px 0 8px 0" }),
        metaEditor,
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
            return missions;
        } catch (err) {
            console.error("Failed to load missions:", err);
            missionList.el.innerHTML = "";
            missionList.add(
                new UI.Text(`❌ Fehler beim Laden der Missionen: ${err.message}`)
                    .setStyle({ color: "var(--ui-color-error)" })
            );
            return [];
        }
    }

    function _extractModId(input) {
        if (!input) return null;
        const urlMatch = input.match(/id=(\d+)/);
        if (urlMatch) return urlMatch[1];
        if (/^\d+$/.test(input)) return input;
        const looseMatch = input.match(/(\d{6,})/);
        return looseMatch ? looseMatch[1] : null;
    }

    function _parseModIds(text) {
        const lines = String(text || "")
            .split("\n")
            .map(l => l.trim())
            .filter(l => l.length > 0);
        const ids = [];
        const seen = new Set();
        for (const line of lines) {
            const id = _extractModId(line);
            if (id && !seen.has(id)) {
                seen.add(id);
                ids.push(id);
            }
        }
        return ids;
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

    uploadBtn.onClick(async () => {
        if (!selectedConfig) {
            alert("Bitte zuerst eine Konfiguration auswählen");
            return;
        }
        const file = missionFileInput.files[0];
        if (!file) {
            alert("Bitte eine Mission-Datei auswählen");
            return;
        }

        uploadBtn.setDisabled(true);
        uploadStatus.setText("Upload läuft...");

        try {
            const missionName = missionNameInput.value.trim();
            const description = missionDescInput.el.value.trim();
            const resp = await apiClient.uploadMission({
                file,
                configName: selectedConfig,
                missionName: missionName || undefined,
                description: description || undefined
            });

            if (!resp.ok) {
                // Handle 409 conflict - duplicate file
                if (resp.status === 409) {
                    throw new Error(resp.detail || "Mission mit identischem Inhalt existiert bereits");
                }
                throw new Error(resp.detail || "Upload fehlgeschlagen");
            }

            uploadStatus.setText(`✅ Mission hochgeladen: ${resp.mission?.name || file.name}`);
            missionFileInput.value = "";
            missionNameInput.value = "";
            missionDescInput.setValue("");

            await loadMissionsForConfig(selectedConfig);
        } catch (err) {
            uploadStatus.setText(`❌ ${err.message}`);
        } finally {
            uploadBtn.setDisabled(false);
        }
    });
    
    function formatUploadDate(isoString) {
        if (!isoString) return "Datum unbekannt";
        try {
            const date = new Date(isoString);
            return date.toLocaleDateString("de-DE", {
                day: "2-digit",
                month: "short",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit"
            });
        } catch (e) {
            return "Datum unbekannt";
        }
    }
    
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
                }),
                new UI.Text(`📅 ${formatUploadDate(mission.uploadedAt)}`).setStyle({
                    fontSize: "0.75em",
                    color: "var(--ui-color-text-muted)"
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
                selectedMissionData = mission;
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
        missionFileInfo.setText(`Datei: ${mission.file || "—"}`);
        missionUploadedInfo.setText(`Uploaded: ${mission.uploadedAt || "—"}`);

        metaDescInput.setValue(mission.description || "");

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
        
        metaEditor.el.innerHTML = "";
        metaEditor.add(
            new UI.Text("Beschreibung:").setStyle({ fontSize: "0.85em", fontWeight: "600" }),
            metaDescInput,
            new UI.HDiv({ gap: 8, align: "center" }).add(saveMetaBtn, saveMetaStatus)
        );
    }

    saveMetaBtn.onClick(async () => {
        if (!selectedConfig || !selectedMissionData) return;

        saveMetaBtn.setDisabled(true);
        saveMetaStatus.setText("Speichern...");

        try {
            const payload = {
                name: selectedMissionData.name,
                file: selectedMissionData.file || undefined,
                configName: selectedConfig,
                description: metaDescInput.el.value.trim() || undefined
            };

            const resp = await apiClient.saveMissionMeta(payload);
            if (!resp.ok) throw new Error(resp.detail || "Speichern fehlgeschlagen");

            saveMetaStatus.setText("✅ Gespeichert");

            const updatedList = await loadMissionsForConfig(selectedConfig);
            const updated = updatedList.find(m => m.name === selectedMissionData.name) || updatedList.find(m => m.file === selectedMissionData.file);
            if (updated) {
                selectedMission = updated.name;
                selectedMissionData = updated;
                displayMissionDetails(updated);
                detailsSection.setStyle({ display: "block" });
            }
        } catch (err) {
            saveMetaStatus.setText(`❌ Fehler: ${err.message}`);
        } finally {
            saveMetaBtn.setDisabled(false);
        }
    });
    
    // Initial load
    loadConfigs();
    
    return container;
}

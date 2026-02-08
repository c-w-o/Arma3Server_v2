import * as UI from "/ui-kit-0/src/ui-kit-0.js";
import { apiClient } from "./api/client.js";

export function createDashboardContent() {
    const container = new UI.VDiv({ gap: 16 });
    
    // State
    let selectedConfig = null;
    let selectedMission = null;
    let allConfigs = [];
    let missions = [];
    
    // ===== Header =====
    container.add(
        new UI.Heading("Dashboard", { level: 2 }).setStyle({ margin: "0 0 16px 0" })
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
        
        if (selectedConfig) {
            await loadMissionsForConfig(selectedConfig);
            missionSection.setStyle({ display: "block" });
        } else {
            missionSection.setStyle({ display: "none" });
        }
    });
    
    configSection.add(configSelect);
    container.add(configSection);
    
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
        new UI.Heading("2. Mission auswählen", { level: 4 }).setStyle({ margin: "0 0 12px 0" })
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

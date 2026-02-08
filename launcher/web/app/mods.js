import * as UI from "/ui-kit-0/src/ui-kit-0.js";
import { apiClient } from "./api/client.js";

export function createModsContent() {
    const container = new UI.VDiv({ gap: 12 });
    
    // Get global store
    const globalStore = UI.AppMain.getInstance()._store;
    
    // Header with title
    const headerRow = new UI.HDiv({ gap: 12, align: "center" });
    headerRow.add(
        new UI.Heading("Mods", { level: 3 })
    );
    
    container.add(headerRow);

    // Container for dropdown and tables
    const contentArea = new UI.VDiv({ gap: 12 });
    
    // Dropdown for selecting config
    const dropdown = new UI.Select({ placeholder: "Select a configuration..." });
    dropdown.bind(globalStore, "activeConfig");

    // HTML Preset Import/Export Section
    let currentPresetConfig = null;
    const presetSection = new UI.VDiv({ gap: 12 });
    presetSection.setStyle({
        border: "2px solid var(--ui-color-primary)",
        borderRadius: "var(--ui-radius-md)",
        padding: "16px",
        background: "var(--ui-color-surface-variant)",
        display: "none"
    });

    presetSection.add(
        new UI.Heading("HTML Preset Import/Export", { level: 5 }).setStyle({ margin: "0 0 12px 0" })
    );

    const downloadRow = new UI.HDiv({ gap: 8, align: "stretch" });

    const downloadAllBtn = new UI.Button("⬇ Download Mod Preset (mit optionalen Mods)");
    downloadAllBtn.setStyle({ flex: "1", padding: "10px" });
    downloadAllBtn.onClick(() => {
        if (!currentPresetConfig) {
            alert("Bitte wählen Sie eine Konfiguration aus.");
            return;
        }
        window.location.href = `/config/${currentPresetConfig}/preset-all.html`;
    });

    const downloadBaseBtn = new UI.Button("⬇ Download Mod Preset (nur Pflicht)");
    downloadBaseBtn.setStyle({ flex: "1", padding: "10px" });
    downloadBaseBtn.onClick(() => {
        if (!currentPresetConfig) {
            alert("Bitte wählen Sie eine Konfiguration aus.");
            return;
        }
        window.location.href = `/config/${currentPresetConfig}/preset-base.html`;
    });

    downloadRow.add(downloadAllBtn, downloadBaseBtn);
    presetSection.add(downloadRow);

    const uploadLabel = new UI.Text("HTML Preset hochladen (wird abgeglichen und bereinigt):");
    uploadLabel.setStyle({ fontSize: "0.9em", margin: "8px 0 4px 0" });

    const uploadRow = new UI.HDiv({ gap: 8, align: "stretch" });
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = ".html";
    fileInput.style.flex = "1";
    fileInput.style.padding = "8px";

    const uploadBtn = new UI.Button("📤 Upload & Bereinigen");
    uploadBtn.setStyle({ padding: "8px 16px" });
    uploadBtn.onClick(async () => {
        const file = fileInput.files[0];
        if (!file) {
            alert("Bitte wählen Sie eine HTML-Datei aus.");
            return;
        }
        if (!currentPresetConfig) {
            alert("Bitte wählen Sie eine Konfiguration aus.");
            return;
        }

        uploadBtn.setDisabled(true);
        uploadBtn.setText("Verarbeite...");

        try {
            const formData = new FormData();
            formData.append("file", file);

            const resp = await fetch(`/config/${currentPresetConfig}/import-preset`, {
                method: "POST",
                body: formData
            });

            if (!resp.ok) {
                const error = await resp.json();
                throw new Error(error.detail || "Upload fehlgeschlagen");
            }

            const result = await resp.json();

            if (result.ok && result.data && result.data.sanitizedHtml) {
                const blob = new Blob([result.data.sanitizedHtml], { type: "text/html" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `${currentPresetConfig}_sanitized.html`;
                a.click();
                URL.revokeObjectURL(url);

                alert(`✅ ${result.detail}\n\nBereinigte HTML wurde heruntergeladen.`);
            } else {
                alert("Upload erfolgreich, aber keine bereinigte HTML erhalten.");
            }

            fileInput.value = "";
        } catch (err) {
            alert(`Fehler beim Upload: ${err.message}`);
        } finally {
            uploadBtn.setDisabled(false);
            uploadBtn.setText("📤 Upload & Bereinigen");
        }
    });

    uploadRow.add(fileInput, uploadBtn);
    presetSection.add(uploadLabel, uploadRow);

    function setPresetConfig(configName) {
        currentPresetConfig = configName || null;
        presetSection.el.style.display = currentPresetConfig ? "block" : "none";
    }
    
    // Table containers
    const modsAndMapsTable = new UI.TableView();
    modsAndMapsTable.setColumns([
        { key: "name", label: "Name" },
        { key: "id", label: "ID" }
    ]);
    modsAndMapsTable.onRowClick((row) => {
        if (row.id) {
            const steamUrl = `https://steamcommunity.com/sharedfiles/filedetails/?id=${row.id}`;
            window.open(steamUrl, "_blank");
        }
    });
    
    const clientModsTable = new UI.TableView();
    clientModsTable.setColumns([
        { key: "name", label: "Name" },
        { key: "id", label: "ID" }
    ]);
    clientModsTable.onRowClick((row) => {
        if (row.id) {
            const steamUrl = `https://steamcommunity.com/sharedfiles/filedetails/?id=${row.id}`;
            window.open(steamUrl, "_blank");
        }
    });
    
    const serverModsTable = new UI.TableView();
    serverModsTable.setColumns([
        { key: "name", label: "Name" },
        { key: "id", label: "ID" }
    ]);
    serverModsTable.onRowClick((row) => {
        if (row.id) {
            const steamUrl = `https://steamcommunity.com/sharedfiles/filedetails/?id=${row.id}`;
            window.open(steamUrl, "_blank");
        }
    });
    
    const dlcsList = new UI.VDiv({ gap: 6 });
    
    // Fetch configs automatically
    async function loadConfigs() {
        try {
            // Use centralized API client to fetch configs
            const data = await apiClient.getConfigs();
            
            if (!data.ok) throw new Error(data.detail || "Unknown error");
            
            const configs = data.configs || [];
            const activeConfig = data.active;
            
            // Store in global store
            const store = globalStore;
            store.setPath("configs", configs);
            store.setPath("activeConfig", activeConfig);
            
        } catch (error) {
            console.error("Error loading configs:", error);
            const store = globalStore;
            store.setPath("configs", []);
            store.setPath("activeConfig", null);
        }
    }
    
    function displayModsForConfig(configName, configs) {
        const config = configs.find(c => c.name === configName);
        if (!config) {
            setPresetConfig(null);
            return;
        }
        
        setPresetConfig(configName);
        
        console.log("Config:", config); // Debug: Check if dlcs are in config
        
        // Clear tables
        modsAndMapsTable.setData([]);
        clientModsTable.setData([]);
        serverModsTable.setData([]);
        dlcsList.clear();
        
        // Populate mods and maps table
        const workshop = config.workshop || {};
        const mods = (workshop.mods || []).map(mod => ({ name: mod.name, id: mod.id }));
        const maps = (workshop.maps || []).map(map => ({ name: map.name, id: map.id }));
        modsAndMapsTable.setData([...mods, ...maps]);
        
        // Populate client mods table
        const clientMods = (workshop.clientmods || []).map(mod => ({ name: mod.name, id: mod.id }));
        clientModsTable.setData(clientMods);
        
        // Populate server mods table
        const serverMods = (workshop.servermods || []).map(mod => ({ name: mod.name, id: mod.id }));
        serverModsTable.setData(serverMods);
        
        // Populate DLCs list
        const dlcs = config.dlcs || [];
        if (dlcs.length === 0) {
            dlcsList.add(new UI.Text("No DLCs"));
        } else {
            dlcs.forEach(dlc => {
                dlcsList.add(new UI.Text(`${dlc.name} (${dlc.mount})`));
            });
        }
    }
    
    // Add header for mods and maps
    const modsHeader = new UI.Heading("Mods & Maps", { level: 4 });
    
    // Add header for client mods
    const clientHeader = new UI.Heading("Client Mods", { level: 4 });
    
    // Add header for server mods
    const serverHeader = new UI.Heading("Server Mods", { level: 4 });
    
    // Add header for DLCs
    const dlcHeader = new UI.Heading("DLCs", { level: 4 });
    
    contentArea.add(
        dropdown,
        presetSection,
        modsHeader,
        modsAndMapsTable,
        clientHeader,
        clientModsTable,
        serverHeader,
        serverModsTable,
        dlcHeader,
        dlcsList
    );
    
    container.add(contentArea);
    
    // Bind to store
    const store = globalStore;
    store.subscribePath("configs", (configs) => {
        dropdown.clearOptions();
        dropdown.addOption("Select a configuration...", "");
        (configs || []).forEach((config) => {
            dropdown.addOption(config.name, config.name);
        });
    });
    store.subscribePath("activeConfig", (active) => {
        const configs = store.getPath("configs") || [];
        displayModsForConfig(active, configs);
    });
    
    // Handle dropdown change
    dropdown.on("change", () => {
        const selectedName = dropdown.getValue();
        store.setPath("activeConfig", selectedName);
    });
    
    // Load configs automatically when content is created
    loadConfigs();
    
    return container;
}

import * as UI from "/ui-kit-0/src/ui-kit-0.js";

// Create REST client instance
const rpcClient = new UI.RestClient("", {
    callTimeoutMs: 10000,
    retries: 2,
});

export function createModsContent() {
    const container = new UI.VDiv({ gap: 12 });
    
    // Header with title and update button
    const headerRow = new UI.HDiv({ gap: 12, align: "center" });
    headerRow.add(
        new UI.Heading("Mods", { level: 3 })
    );
    
    // Store updateBtn in outer scope so loadConfigs can reference it
    let updateBtn = null;
    
    container.add(headerRow);

    // Container for dropdown and tables
    const contentArea = new UI.VDiv({ gap: 12 });
    
    // Dropdown for selecting config
    const dropdown = new UI.Select({ placeholder: "Select a configuration..." });
    dropdown.setValue("");
    
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
    
    // Create update button and add to header
    updateBtn = new UI.Button("Update");
    updateBtn.onClick(() => loadConfigs());
    headerRow.add(updateBtn);
    
    // Fetch configs on demand
    async function loadConfigs() {
        try {
            // Disable button while loading
            if (updateBtn) updateBtn.setDisabled(true);
            
            // Use rpcClient to fetch configs via POST
            const data = await rpcClient.get("/configs", {});
            
            if (!data.ok) throw new Error(data.detail || "Unknown error");
            
            const configs = data.configs || [];
            const activeConfig = data.active;
            
            // Populate dropdown with options
            dropdown.clearOptions();
            dropdown.addOption("Select a configuration...", "");
            
            configs.forEach((config) => {
                dropdown.addOption(config.name, config.name);
            });
            
            // Set active config as selected
            if (activeConfig) {
                dropdown.setValue(activeConfig);
                displayModsForConfig(activeConfig, configs);
            }
            
        } catch (error) {
            console.error("Error loading configs:", error);
            dlcsList.clear();
            dlcsList.add(new UI.Text(`Error: ${error.message}`));
        } finally {
            // Re-enable button
            if (updateBtn) updateBtn.setDisabled(false);
        }
    }
    
    function displayModsForConfig(configName, configs) {
        const config = configs.find(c => c.name === configName);
        if (!config) return;
        
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
    
    // Handle dropdown change
    dropdown.on("change", () => {
        const selectedName = dropdown.getValue();
        if (selectedName) {
            // Fetch configs again to get fresh data
            rpcClient.get("/configs", {})
                .then(data => {
                    if (data.ok) {
                        displayModsForConfig(selectedName, data.configs || []);
                    }
                })
                .catch(err => console.error("Error fetching configs:", err));
        }
    });
    
    // Store the loadConfigs function on the container for later access
    // This will be called when the Mods tab is clicked
    container.loadModsData = loadConfigs;
    
    return container;
}

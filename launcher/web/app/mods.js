import * as UI from "/ui-kit-0/src/ui-kit-0.js";

// Create REST client instance
const rpcClient = new UI.RestClient("", {
    callTimeoutMs: 10000,
    retries: 2,
});

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
            // Use rpcClient to fetch configs via POST
            const data = await rpcClient.get("/configs", {});
            
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

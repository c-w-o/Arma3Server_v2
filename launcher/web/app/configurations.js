import * as UI from "/ui-kit-0/src/ui-kit-0.js";

// Create REST client for API calls
const rpcClient = new UI.RestClient("", {
    callTimeoutMs: 10000,
    retries: 2,
});

export function createConfigurationsContent() {
    const container = new UI.VDiv({ gap: 12 });
    
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
    
    // Placeholder for config list (wird von API geladen)
    const configList = new UI.VDiv({ gap: 4 });
    configList.add(
        new UI.Button("production").setStyle({ width: "100%", textAlign: "left" }),
        new UI.Button("event").setStyle({ width: "100%", textAlign: "left" }),
        new UI.Button("testing").setStyle({ width: "100%", textAlign: "left" })
    );
    listDiv.add(configList);
    
    mainLayout.add(listDiv);
    
    // === RIGHT: Editor Tabs ===
    const editorDiv = new UI.VDiv({ gap: 12 });
    editorDiv.setStyle({ flex: "1" });
    
    const tabs = new UI.Tabs();
    
    // Tab 1: Basis (read-only)
    const basisContent = new UI.VDiv({ gap: 8 }).add(
        new UI.Heading("Basis-Konfiguration (Defaults)", { level: 4 }).setStyle({ margin: "0" }),
        new UI.Text("Diese Einstellungen gelten für alle Konfigurationen.").setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)" }),
        
        new UI.HDiv({ gap: 12, align: "start" }).add(
            new UI.VDiv({ gap: 8 }).add(
                new UI.Heading("Server", { level: 5 }).setStyle({ margin: "0" }),
                new UI.HDiv({ gap: 8, align: "center" }).add(
                    new UI.Span("Hostname:").setStyle({ minWidth: "100px" }),
                    new UI.TextField("", { placeholder: "Arma 3 Dedicated Server" }).setStyle({ flex: "1" })
                ),
                new UI.HDiv({ gap: 8, align: "center" }).add(
                    new UI.Span("Port:").setStyle({ minWidth: "100px" }),
                    new UI.TextField("2302", { type: "number" }).setStyle({ width: "100px" })
                ),
                new UI.HDiv({ gap: 8, align: "center" }).add(
                    new UI.Span("Max Players:").setStyle({ minWidth: "100px" }),
                    new UI.TextField("60", { type: "number" }).setStyle({ width: "100px" })
                )
            ),
            new UI.VDiv({ gap: 8 }).add(
                new UI.Heading("Mods (Defaults)", { level: 5 }).setStyle({ margin: "0" }),
                new UI.Text("baseMods: 37").setStyle({ fontSize: "0.9em" }),
                new UI.Text("serverMods: 1").setStyle({ fontSize: "0.9em" }),
                new UI.Text("clientMods: 12").setStyle({ fontSize: "0.9em" }),
                new UI.Text("maps: 1").setStyle({ fontSize: "0.9em" })
            )
        ),
        new UI.Button("Basis editieren").setStyle({ marginTop: "12px" })
    );
    
    // Tab 2: Config-Overrides
    const overridesContent = new UI.VDiv({ gap: 8 }).add(
        new UI.Heading("Config-spezifische Overrides", { level: 4 }).setStyle({ margin: "0" }),
        new UI.Text("Änderungen gegen die Basis-Konfiguration.").setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)" }),
        
        new UI.VDiv({ gap: 8 }).add(
            new UI.Heading("Mods", { level: 5 }).setStyle({ margin: "0 0 6px 0" }),
            new UI.Table({
                columns: [
                    { label: "Kategorie", key: "category" },
                    { label: "Änderung", key: "change" },
                    { label: "Anzahl", key: "count" }
                ],
                data: [
                    { category: "baseMods", change: "+ Advanced Rappelling", count: "+1" },
                    { category: "minus_mods", change: "- RHS GREF", count: "1 removed" }
                ]
            }).setStyle({ width: "100%" })
        ),
        
        new UI.HDiv({ gap: 8 }).add(
            new UI.Button("Mods editieren"),
            new UI.Button("Revert").setStyle({ background: "var(--ui-color-surface)", color: "var(--ui-color-text)" })
        ).setStyle({ marginTop: "12px" })
    );
    
    // Tab 3: Merged Preview
    const previewContent = new UI.VDiv({ gap: 8 }).add(
        new UI.Heading("Merged Preview", { level: 4 }).setStyle({ margin: "0" }),
        new UI.Text("Kombinierte Konfiguration (Basis + Overrides).").setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)" }),
        
        new UI.Table({
            columns: [
                { label: "Kategorie", key: "category" },
                { label: "Anzahl", key: "count" },
                { label: "Details", key: "details" }
            ],
            data: [
                { category: "baseMods", count: "38", details: "37 base + 1 added" },
                { category: "serverMods", count: "1", details: "nur base" },
                { category: "clientMods", count: "12", details: "nur base" },
                { category: "minus_mods", count: "1", details: "RHS GREF" }
            ]
        }).setStyle({ width: "100%", marginBottom: "12px" }),
        
        new UI.Button("Full List anzeigen")
    );
    
    tabs.addTab("basis", "Basis", basisContent);
    tabs.addTab("overrides", "Overrides", overridesContent);
    tabs.addTab("merged", "Merged", previewContent);
    
    editorDiv.add(tabs);
    
    mainLayout.add(editorDiv);
    container.add(mainLayout);
    
    // Bottom: Save/Cancel
    container.add(
        new UI.HDiv({ gap: 8 }).add(
            new UI.Button("Save").setStyle({ padding: "8px 16px" }),
            new UI.Button("Cancel").setStyle({ padding: "8px 16px", background: "var(--ui-color-surface)", color: "var(--ui-color-text)" })
        )
    );
    
    return container;
}

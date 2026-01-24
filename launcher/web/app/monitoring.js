import * as UI from "/ui-kit-0/src/ui-kit-0.js";

export function createMonitoringContent() {
    const container = new UI.VDiv({ gap: 12 });
    
    // Header
    container.add(
        new UI.Heading("Monitoring", { level: 3 })
    );
    
    // Time range selector
    const timeRangeDiv = new UI.HDiv({ gap: 8, align: "center" });
    timeRangeDiv.add(
        new UI.Span("Zeitraum:").setStyle({ fontWeight: "600" }),
        new UI.Button("15m"),
        new UI.Button("1h"),
        new UI.Button("6h"),
        new UI.Button("24h"),
        new UI.HSpacer(),
        new UI.Button("🔄 Auto-Refresh")
    );
    container.add(timeRangeDiv);
    
    // Charts placeholder
    const chartsGrid = new UI.HDiv({ gap: 12 });
    chartsGrid.setStyle({ display: "flex", flexWrap: "wrap" });
    
    // Chart cards
    const chartCard = (title) => {
        const card = new UI.VDiv({ gap: 8 });
        card.setStyle({
            flex: "1 1 calc(50% - 6px)",
            minWidth: "300px",
            background: "var(--ui-color-surface)",
            border: "1px solid var(--ui-color-border)",
            borderRadius: "var(--ui-radius-md)",
            padding: "12px"
        });
        card.add(
            new UI.Heading(title, { level: 4 }).setStyle({ margin: "0 0 12px 0" }),
            new UI.VDiv().setStyle({
                height: "200px",
                background: "var(--ui-color-surface-muted)",
                borderRadius: "var(--ui-radius-md)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--ui-color-text-muted)"
            }).add(
                new UI.Text("Chart wird über WebSocket aktualisiert")
            )
        );
        return card;
    };
    
    chartsGrid.add(
        chartCard("CPU Auslastung (%)"),
        chartCard("RAM Auslastung (MB)"),
        chartCard("Netzwerk (In/Out)"),
        chartCard("Disk I/O")
    );
    
    container.add(chartsGrid);
    
    // Events log
    container.add(
        new UI.Heading("Events", { level: 4 }).setStyle({ marginTop: "12px" }),
        new UI.VDiv().setStyle({
            height: "150px",
            background: "var(--ui-color-surface)",
            border: "1px solid var(--ui-color-border)",
            borderRadius: "var(--ui-radius-md)",
            padding: "12px",
            overflowY: "auto",
            fontSize: "0.9em",
            color: "var(--ui-color-text-muted)"
        }).add(
            new UI.Text("Restart/Config-Wechsel/Mod-Update Marker werden hier angezeigt")
        )
    );
    
    return container;
}

import * as UI from "/ui-kit-0/src/ui-kit-0.js";

export function createDashboardContent() {
    const container = new UI.VDiv({ gap: 16 });
    
    // ===== Quick Actions =====
    const quickActionsDiv = new UI.VDiv({ gap: 8 });
    quickActionsDiv.add(
        new UI.Heading("Quick Actions", { level: 4 }).setStyle({ margin: "0" }),
        new UI.HDiv({ gap: 8, align: "center" }).add(
            new UI.Span("Aktive Config:").setStyle({ fontWeight: "600" }),
            new UI.Select({ placeholder: "Wähle Konfiguration..." }).setStyle({ flex: "1", maxWidth: "300px" }),
            new UI.Button("Start").setStyle({ padding: "8px 16px" }),
            new UI.Button("Stop").setStyle({ padding: "8px 16px" }),
            new UI.Button("Restart").setStyle({ padding: "8px 16px" })
        )
    );
    quickActionsDiv.setStyle({
        background: "var(--ui-color-surface)",
        border: "1px solid var(--ui-color-border)",
        borderRadius: "var(--ui-radius-md)",
        padding: "12px"
    });
    container.add(quickActionsDiv);
    
    // ===== Summary Cards (2x2 Grid) =====
    const summaryGrid = new UI.HDiv({ gap: 12 });
    summaryGrid.setStyle({ display: "flex", flexWrap: "wrap" });
    
    const summaryCard = (title, content, icon = "📊") => {
        const card = new UI.VDiv({ gap: 6 });
        card.setStyle({
            flex: "1 1 calc(50% - 6px)",
            minWidth: "250px",
            background: "var(--ui-color-surface)",
            border: "1px solid var(--ui-color-border)",
            borderRadius: "var(--ui-radius-md)",
            padding: "12px"
        });
        card.add(
            new UI.HDiv({ gap: 8, align: "center" }).add(
                new UI.Span(icon).setStyle({ fontSize: "1.5em" }),
                new UI.Heading(title, { level: 4 }).setStyle({ margin: "0" })
            ),
            content
        );
        return card;
    };
    
    // Active Profile Card
    const profileContent = new UI.VDiv({ gap: 4 }).add(
        new UI.Text("Profile: Production").setStyle({ fontWeight: "600" }),
        new UI.Text("Basis: Arma3-Base").setStyle({ fontSize: "0.9em" }),
        new UI.HDiv({ gap: 4 }).add(
            new UI.Span("Erweiterungen:").setStyle({ fontSize: "0.85em" }),
            new UI.Span("ACE").setStyle({ 
                fontSize: "0.75em", 
                background: "var(--ui-color-nav-active)", 
                color: "white", 
                padding: "2px 6px", 
                borderRadius: "3px" 
            }),
            new UI.Span("CBA").setStyle({ 
                fontSize: "0.75em", 
                background: "var(--ui-color-nav-active)", 
                color: "white", 
                padding: "2px 6px", 
                borderRadius: "3px" 
            })
        )
    );
    summaryGrid.add(summaryCard("Active Profile", profileContent, "⚙️"));
    
    // Modset Card
    const modsetContent = new UI.VDiv({ gap: 4 }).add(
        new UI.Text("124 Mods").setStyle({ fontWeight: "600", color: "var(--ui-color-accent)" }),
        new UI.HDiv({ gap: 8 }).add(
            new UI.Span("3 optional").setStyle({ fontSize: "0.9em" }),
            new UI.Span("Hash OK").setStyle({ fontSize: "0.9em", color: "var(--ui-color-ok)" })
        )
    );
    summaryGrid.add(summaryCard("Modset", modsetContent, "📦"));
    
    // Server Health Card
    const healthContent = new UI.VDiv({ gap: 4 }).add(
        new UI.Text("Uptime: 5d 2h").setStyle({ fontSize: "0.9em" }),
        new UI.HDiv({ gap: 12 }).add(
            new UI.VDiv({ gap: 2 }).add(
                new UI.Span("CPU").setStyle({ fontSize: "0.75em", color: "var(--ui-color-text-muted)" }),
                new UI.Span("45%").setStyle({ fontWeight: "600" })
            ),
            new UI.VDiv({ gap: 2 }).add(
                new UI.Span("RAM").setStyle({ fontSize: "0.75em", color: "var(--ui-color-text-muted)" }),
                new UI.Span("8.2 GB").setStyle({ fontWeight: "600" })
            ),
            new UI.VDiv({ gap: 2 }).add(
                new UI.Span("FPS").setStyle({ fontSize: "0.75em", color: "var(--ui-color-text-muted)" }),
                new UI.Span("58").setStyle({ fontWeight: "600" })
            )
        )
    );
    summaryGrid.add(summaryCard("Server Health", healthContent, "💚"));
    
    // Players Card
    const playersContent = new UI.VDiv({ gap: 4 }).add(
        new UI.Text("12/60 online").setStyle({ fontWeight: "600", fontSize: "1.1em", color: "var(--ui-color-accent)" }),
        new UI.Text("Peak today: 45").setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)" })
    );
    summaryGrid.add(summaryCard("Players", playersContent, "👥"));
    
    container.add(summaryGrid);
    
    // ===== Monitoring Section =====
    const monitoringDiv = new UI.VDiv({ gap: 8 });
    monitoringDiv.add(
        new UI.HDiv({ gap: 8, align: "center" }).add(
            new UI.Heading("Monitoring", { level: 4 }).setStyle({ margin: "0" }),
            new UI.HSpacer(),
            new UI.Button("15m").setStyle({ padding: "4px 8px", fontSize: "0.9em" }),
            new UI.Button("1h").setStyle({ padding: "4px 8px", fontSize: "0.9em" }),
            new UI.Button("6h").setStyle({ padding: "4px 8px", fontSize: "0.9em" })
        )
    );
    
    // Mini charts
    const miniChartsGrid = new UI.HDiv({ gap: 8 });
    miniChartsGrid.setStyle({ display: "flex", flexWrap: "wrap" });
    
    const miniChart = (title) => {
        const chart = new UI.VDiv({ gap: 6 });
        chart.setStyle({
            flex: "1 1 calc(50% - 4px)",
            minWidth: "200px",
            background: "var(--ui-color-surface)",
            border: "1px solid var(--ui-color-border)",
            borderRadius: "var(--ui-radius-md)",
            padding: "8px"
        });
        chart.add(
            new UI.Span(title).setStyle({ fontSize: "0.9em", fontWeight: "600" }),
            new UI.VDiv().setStyle({
                height: "80px",
                background: "var(--ui-color-surface-muted)",
                borderRadius: "4px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--ui-color-text-muted)",
                fontSize: "0.8em"
            }).add(
                new UI.Text("Chart wird aktualisiert...")
            )
        );
        return chart;
    };
    
    miniChartsGrid.add(
        miniChart("CPU"),
        miniChart("RAM"),
        miniChart("Netzwerk"),
        miniChart("Disk I/O")
    );
    
    monitoringDiv.add(miniChartsGrid);
    monitoringDiv.setStyle({
        background: "var(--ui-color-surface)",
        border: "1px solid var(--ui-color-border)",
        borderRadius: "var(--ui-radius-md)",
        padding: "12px"
    });
    container.add(monitoringDiv);
    
    // ===== Activity Feed =====
    const activityDiv = new UI.VDiv({ gap: 8 });
    activityDiv.add(
        new UI.Heading("Activity Feed", { level: 4 }).setStyle({ margin: "0" }),
        new UI.VDiv().setStyle({
            background: "var(--ui-color-surface)",
            border: "1px solid var(--ui-color-border)",
            borderRadius: "var(--ui-radius-md)",
            padding: "12px",
            maxHeight: "200px",
            overflowY: "auto",
            fontSize: "0.9em",
            display: "flex",
            flexDirection: "column",
            gap: "6px"
        }).add(
            new UI.Text("20:15 - Server started with Profile 'Production'"),
            new UI.Text("20:10 - Mod update completed (124 mods)"),
            new UI.Text("20:05 - Player joined: PlayerOne"),
            new UI.Text("19:55 - Config changed: Production (Requires restart: No)"),
            new UI.Text("19:45 - Validation OK")
        )
    );
    container.add(activityDiv);
    
    return container;
}


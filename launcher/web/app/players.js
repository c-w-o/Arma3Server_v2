import * as UI from "/ui-kit-0/src/ui-kit-0.js";

export function createPlayersContent() {
    const container = new UI.VDiv({ gap: 12 });
    
    // Header with stats
    const headerDiv = new UI.HDiv({ gap: 12, align: "center" });
    headerDiv.add(
        new UI.Heading("Spieler", { level: 3 }),
        new UI.HSpacer(),
        new UI.VDiv({ gap: 4 }).add(
            new UI.Span("Online: 12/60").setStyle({ fontSize: "1.2em", fontWeight: "600", color: "var(--ui-color-accent)" }),
            new UI.Span("Peak today: 45").setStyle({ fontSize: "0.9em", color: "var(--ui-color-text-muted)" })
        )
    );
    container.add(headerDiv);
    
    // Player table - using Table (alias for TableView)
    const table = new UI.Table({
        columns: [
            { label: "Name", key: "name" },
            { label: "UID", key: "uid" },
            { label: "Ping (ms)", key: "ping" },
            { label: "Online seit", key: "online_time" },
            { label: "Squad", key: "squad" },
            { label: "Status", key: "status" }
        ],
        data: [
            {
                name: "PlayerOne",
                uid: "76561198012345678",
                ping: "45",
                online_time: "2h 30m",
                squad: "Alpha",
                status: "Alive"
            },
            {
                name: "PlayerTwo",
                uid: "76561198087654321",
                ping: "62",
                online_time: "45m",
                squad: "Bravo",
                status: "Dead"
            }
        ]
    });
    
    container.add(
        new UI.Heading("Online Spieler", { level: 4 }).setStyle({ marginTop: "12px" }),
        table.setStyle({ width: "100%" })
    );
    
    // Player timeline
    container.add(
        new UI.Heading("Aktivität", { level: 4 }).setStyle({ marginTop: "12px" }),
        new UI.VDiv().setStyle({
            background: "var(--ui-color-surface)",
            border: "1px solid var(--ui-color-border)",
            borderRadius: "var(--ui-radius-md)",
            padding: "12px",
            maxHeight: "200px",
            overflowY: "auto",
            fontSize: "0.9em"
        }).add(
            new UI.Text("20:15 - PlayerOne joined"),
            new UI.Text("20:12 - PlayerTwo joined"),
            new UI.Text("20:10 - PlayerThree left"),
            new UI.Text("20:05 - PlayerOne left"),
            new UI.Text("19:55 - PlayerTwo joined")
        ).setStyle({ display: "flex", flexDirection: "column", gap: "4px" })
    );
    
    return container;
}

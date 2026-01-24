import * as UI from "/ui-kit-0/src/ui-kit-0.js";

export function createJobsContent() {
    const container = new UI.VDiv({ gap: 12 });
    
    container.add(
        new UI.Heading("Jobs & Historia", { level: 3 })
    );
    
    // Tabs for running/completed/failed
    const tabs = new UI.Tabs();
    
    const runningContent = new UI.VDiv({ gap: 8 }).add(
        new UI.Heading("Laufende Jobs", { level: 4 }),
        new UI.VDiv().setStyle({
            background: "var(--ui-color-surface)",
            border: "1px solid var(--ui-color-border)",
            borderRadius: "var(--ui-radius-md)",
            padding: "12px"
        }).add(
            new UI.Text("Update Modset... 45%"),
            new UI.VDiv().setStyle({
                width: "100%",
                height: "8px",
                background: "var(--ui-color-surface-muted)",
                borderRadius: "4px",
                overflow: "hidden"
            }).add(
                new UI.VDiv().setStyle({
                    width: "45%",
                    height: "100%",
                    background: "var(--ui-color-accent)"
                })
            )
        )
    );
    
    const completedContent = new UI.VDiv({ gap: 8 }).add(
        new UI.Heading("Abgeschlossene Jobs", { level: 4 }),
        new UI.Text("✓ Server Started - 2025-01-24 20:15"),
        new UI.Text("✓ Mod Validation - 2025-01-24 19:45"),
        new UI.Text("✓ Config Switched - 2025-01-24 18:30")
    );
    
    const failedContent = new UI.VDiv({ gap: 8 }).add(
        new UI.Heading("Fehlgeschlagene Jobs", { level: 4 }),
        new UI.Text("✗ Backup Creation - 2025-01-23 03:00")
    );
    
    tabs.addTab("running", "Laufend", runningContent);
    tabs.addTab("completed", "Abgeschlossen", completedContent);
    tabs.addTab("failed", "Fehler", failedContent);
    
    container.add(tabs);
    
    return container;
}

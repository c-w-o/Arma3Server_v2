import * as UI from "/ui-kit-0/src/ui-kit-0.js";

export function createSettingsContent() {
    const container = new UI.VDiv({ gap: 12 });
    
    container.add(
        new UI.Heading("Einstellungen", { level: 3 })
    );
    
    // Settings sections
    const sections = new UI.VDiv({ gap: 16 });
    
    // System settings
    const systemSection = new UI.VDiv({ gap: 8 });
    systemSection.add(
        new UI.Heading("System", { level: 4 }),
        new UI.HDiv({ gap: 8, align: "center" }).add(
            new UI.Span("Server Pfad:").setStyle({ minWidth: "150px" }),
            new UI.TextField("", { placeholder: "/opt/arma3" }).setStyle({ flex: "1" })
        ),
        new UI.HDiv({ gap: 8, align: "center" }).add(
            new UI.Span("RCON Port:").setStyle({ minWidth: "150px" }),
            new UI.TextField("2302", { placeholder: "2302" }).setStyle({ width: "100px" })
        ),
        new UI.HDiv({ gap: 8, align: "center" }).add(
            new UI.Span("Workshop API Key:").setStyle({ minWidth: "150px" }),
            new UI.TextField("", { placeholder: "••••••••" }).setStyle({ flex: "1" })
        )
    );
    sections.add(systemSection);
    
    // Notification settings
    const notificationSection = new UI.VDiv({ gap: 8 });
    notificationSection.add(
        new UI.Heading("Benachrichtigungen", { level: 4 }),
        new UI.HDiv({ gap: 8, align: "center" }).add(
            new UI.Checkbox(false, { label: "Discord Webhook aktiviert" }),
            new UI.TextField("", { placeholder: "https://discord.com/api/..." }).setStyle({ flex: "1" })
        ),
        new UI.HDiv({ gap: 8, align: "center" }).add(
            new UI.Checkbox(false, { label: "Email bei Fehler" }),
            new UI.TextField("", { placeholder: "admin@example.com" }).setStyle({ flex: "1" })
        )
    );
    sections.add(notificationSection);
    
    // Backup settings
    const backupSection = new UI.VDiv({ gap: 8 });
    backupSection.add(
        new UI.Heading("Backups", { level: 4 }),
        new UI.HDiv({ gap: 8, align: "center" }).add(
            new UI.Span("Täglich um:").setStyle({ minWidth: "150px" }),
            new UI.TextField("03:00", { placeholder: "03:00" }).setStyle({ width: "100px" })
        ),
        new UI.HDiv({ gap: 8, align: "center" }).add(
            new UI.Span("Aufbewahrung:").setStyle({ minWidth: "150px" }),
            new UI.TextField("14", { placeholder: "14" }).setStyle({ width: "100px" }),
            new UI.Span("Tage")
        )
    );
    sections.add(backupSection);
    
    container.add(sections);
    
    // Save button
    container.add(
        new UI.HDiv({ gap: 8 }).add(
            new UI.Button("Speichern"),
            new UI.Button("Abbrechen").setStyle({ background: "var(--ui-color-surface)", color: "var(--ui-color-text)" })
        )
    );
    
    return container;
}

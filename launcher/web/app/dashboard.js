import * as UI from "/ui-kit-0/src/ui-kit-0.js";

export function createDashboardContent() {
    return new UI.VDiv({ gap: 12 }).add(
        new UI.Heading("Dashboard", { level: 3 }),
        new UI.Text("Dashboard content goes here")
    );
}

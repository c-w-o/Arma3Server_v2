import * as UI from "/ui-kit-0/src/ui-kit-0.js";

export function createLogsContent() {
    return new UI.VDiv({ gap: 12 }).add(
        new UI.Heading("Logs", { level: 3 }),
        new UI.Text("Logs content goes here")
    );
}

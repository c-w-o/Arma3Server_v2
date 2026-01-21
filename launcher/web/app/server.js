import * as UI from "/ui-kit-0/src/ui-kit-0.js";

export function createServerContent() {
    return new UI.VDiv({ gap: 12 }).add(
        new UI.Heading("Server Settings", { level: 3 }),
        new UI.Text("Server settings content goes here")
    );
}

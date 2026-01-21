import * as UI from "/ui-kit-0/src/ui-kit-0.js";

export function createModsContent() {
    return new UI.VDiv({ gap: 12 }).add(
        new UI.Heading("Mods", { level: 3 }),
        new UI.Text("Mods content goes here")
    );
}

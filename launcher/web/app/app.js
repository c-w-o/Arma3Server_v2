
export const A3CL_NAME_SHORT = "A3CL";
export const A3CL_NAME_LONG = "Arma3 Control Launcher";
export const A3CL_MAJOR = 0;
export const A3CL_MINOR = 3;
export const A3CL_PATCH = 0;
export const A3CL_VERSION = `${A3CL_MAJOR}.${A3CL_MINOR}.${A3CL_PATCH}`;

import * as UI from "/ui-kit-0/src/ui-kit-0.js";
import { createDashboardContent } from "./dashboard.js";
import { createServerContent } from "./server.js";
import { createModsContent } from "./mods.js";
import { createLogsContent } from "./logs.js";

const app = new UI.AppMain();
// Setup flexbox layout for sticky footer
app.setStyle({ 
	display: "flex",
	flexDirection: "column",
	height: "100vh",
	width: "100%"
});

//const top_banner = app.add(new UI.HDiv());
/*
.-----------------------------------.
| ##### Launcher                    |
| #####                             |
| ##### V0.1                        |
+-----------------------------------+
|       |                           |
|       |                           |
|       |                           |
|       |                           |
|       |                           |
|       |                           |
|       |                           |
|       |                           |
+-------+---------------------------+
|_______|___________________________|

*/
const top_banner = app.add(new UI.HDiv({ gap: 12, align: "center" }));
const middle_banner = app.add(new UI.HDiv());
// Setup left navigation as vertical container with fixed width
const left_navigation = middle_banner.add(new UI.VDiv({ gap: 0 }));
const bottom_banner = app.add(new UI.HDiv({ gap: 12, align: "center" }));

left_navigation.setStyle({ 
	width: "200px", 
	borderRight: "1px solid var(--ui-color-border)",
	overflowY: "auto",
	flexShrink: "0"
});
// Main display area that takes remaining space
const main_display = middle_banner.add(new UI.VDiv());
main_display.setStyle({ 
	flex: "1", 
	overflow: "auto",
	padding: "12px"
});

/* let's fill the top banner */
{
    const logoSvg = `<svg inkscape:version="1.0.2 (e86c870879, 2021-01-15, custom)" sodipodi:docname="Arma_3_game.svg" version="1.1" viewBox="0 0 410.1 185" xmlns="http://www.w3.org/2000/svg" xmlns:cc="http://creativecommons.org/ns#" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"><sodipodi:namedview bordercolor="#666666" borderopacity="1" gridtolerance="10" guidetolerance="10" inkscape:current-layer="layer1" inkscape:cx="-215.47166" inkscape:cy="417.83312" inkscape:pageopacity="0" inkscape:pageshadow="2" inkscape:window-height="1014" inkscape:window-maximized="1" inkscape:window-width="1920" inkscape:window-x="0" inkscape:window-y="36" inkscape:zoom="0.5182245" objecttolerance="10" pagecolor="#ffffff" showgrid="false"/><metadata><rdf:RDF><cc:Work rdf:about=""><dc:format>image/svg+xml</dc:format><dc:type rdf:resource="http://purl.org/dc/dcmitype/StillImage"/><dc:title/></cc:Work></rdf:RDF></metadata><g transform="translate(-46.52 -860.1)"><g transform="matrix(.3685 0 0 .3685 375.7 748)" style="fill: currentColor; color: inherit"><path d="m-565.7 805.1c-0.4444-0.719 4.891-6.548 13.96-15.25l14.68-14.09-0.0171-28.63c-0.0138-23.15 0.2471-28.85 1.365-29.77 1.955-1.623 104.3-1.612 106.2 0.0108 1.88 1.56 2.042 85.82 0.1687 87.69-1.705 1.705-135.3 1.74-136.4 0.0362zm174.8-0.0362c-0.8958-0.8958-1.2-12-1.2-43.8s0.3042-42.9 1.2-43.8c0.903-0.903 14.26-1.2 53.96-1.2 51.68 0 52.79 0.0409 53.83 1.993 0.7204 1.346 0.9753 15.65 0.7852 44.04-0.2415 36.07-0.4945 42.18-1.782 42.99-2.367 1.495-105.3 1.282-106.8-0.2218zm146 0.5414c-0.9732-0.3956-1.25-10.21-1.25-44.32 0-39.03 0.1727-43.88 1.582-44.42 0.87-0.3338 24.86-0.607 53.3-0.607 38.89 0 52.02 0.2976 52.92 1.2 0.876 0.876 1.213 9.043 1.247 30.25l0.047 29.05 14.46 13.47c7.954 7.41 14.31 13.94 14.12 14.5-0.3506 1.052-133.9 1.902-136.4 0.8685zm-648.6-114.7c-0.2869-0.7477 1.878-8.735 4.811-17.75 2.933-9.015 9.224-28.54 13.98-43.39 4.755-14.85 10.83-33.75 13.49-42 2.666-8.25 9.202-28.5 14.52-45s14.11-43.5 19.53-60c7.896-24.05 25.17-77.32 33.56-103.5 0.7932-2.475 1.869-5.175 2.391-6 0.8317-1.315 13.91-1.532 106-1.764 71.88-0.1803 105.7 0.0677 107 0.7852 1.856 0.9935 1.96 2.226 1.96 23.4 0 22.33 2e-3 22.35 2.25 22.95 1.238 0.3316 29.92 0.6109 63.75 0.6207 64.95 0.0187 72.22 0.4331 85.05 4.852 13.61 4.688 23.82 13.08 29.18 23.99l3.268 6.647 0.5-17.16c0.275-9.437 0.7334-17.39 1.019-17.67 0.7985-0.7935 145.7-1.239 146.5-0.4506 0.3853 0.3817 4.062 12.76 8.171 27.5 12.03 43.17 22.22 78.55 22.78 79.12 1.02 1.02 1.651-0.7394 6.603-18.43 2.753-9.834 8.607-30.58 13.01-46.1 4.403-15.52 8.676-30.8 9.496-33.94 0.8198-3.147 1.979-6.31 2.575-7.03 0.8566-1.032 9.006-1.319 38.71-1.365 20.7-0.0317 39.43-0.3765 41.63-0.7662l4-0.7085 0.2691-22.44c0.1969-16.41 0.5995-22.65 1.5-23.23 1.86-1.204 211.4-0.5117 212.6 0.7021 0.5447 0.55 4.205 10.9 8.134 23s15.46 47.65 25.63 79 20.3 62.4 22.51 69c2.209 6.6 5.282 16.05 6.829 21 1.548 4.95 11.21 35.04 21.47 66.86 10.26 31.82 18.42 58.49 18.13 59.25-0.4475 1.166-11.54 1.386-69.31 1.373-37.83-8e-3 -69.39-0.4006-70.13-0.8715-0.7654-0.485-4.847-15.11-9.416-33.73-4.436-18.08-8.553-33.21-9.149-33.62s-10.08-0.6354-21.08-0.5l-20 0.2462-0.2637 33.45c-0.199 25.23-0.5675 33.64-1.5 34.23-0.68 0.4319-35.91 0.7921-78.29 0.8005-58.61 0.0117-77.34-0.2718-78.25-1.185-0.9079-0.9079-1.2-16.53-1.2-64.2 0-36.31-0.3727-62.6-0.8797-62.05-0.7189 0.7764-28.73 98.04-33.83 117.4-0.7941 3.025-2.095 6.512-2.891 7.75l-1.447 2.25h-33.44c-31.36 0-33.5-0.1139-34.42-1.826-1.066-1.991-4.748-15.22-22.6-81.17-6.476-23.92-12.16-43.93-12.63-44.45-0.7587-0.8397-1.41 82.28-0.8778 112.1 0.1201 6.734-0.2466 11.98-0.9261 13.25l-1.125 2.102h-110.9c-109.6 0-110.9-0.0232-112-1.985-0.7062-1.319-1.076-18.17-1.104-50.25-0.0443-51.96-0.1778-53.43-5.223-57.17-2.455-1.82-3.995-2.055-11.94-1.816-5.019 0.1504-9.228 0.3753-9.352 0.4996-0.1243 0.1243-0.465 24.64-0.7571 54.49-0.2921 29.84-0.8046 54.71-1.139 55.25-0.9676 1.566-155.2 1.327-156.1-0.2413-0.4164-0.6737-0.907-15.64-1.09-33.25s-0.53-32.59-0.7706-33.28c-0.3302-0.9439-5.348-1.25-20.49-1.25-19.84 0-20.06 0.0235-21.02 2.25-0.5292 1.238-4.359 16.17-8.51 33.19-4.151 17.01-8.039 31.53-8.639 32.25-1.646 1.983-139.4 1.939-140.2-0.0449zm501.1-159.3-0.2733-17.81-2.419 4.876c-5.337 10.76-18.46 21.14-32.33 25.58-2.062 0.66-3.735 1.503-3.717 1.872 0.0182 0.3698 4.035 2.578 8.925 4.906 12.42 5.916 19.78 12.91 25.3 24.06l4.241 8.563 0.2733-17.11c0.1503-9.413 0.1503-25.13 0-34.93zm439.1 19.16c0.1836-0.1676-1.477-6.98-3.69-15.14-2.213-8.158-5.192-19.56-6.62-25.33-1.428-5.775-3.669-14.1-4.98-18.5-1.311-4.4-3.816-13.62-5.566-20.5s-3.573-13.18-4.05-14c-1.207-2.088-1.392 10.87-1.043 73.2l0.1157 20.7 5.75 0.2999c5.905 0.308 19.49-0.1854 20.08-0.7296zm-740.8-46.97c0-28.19-0.3734-47.5-0.9184-47.5-0.5051 0-1.582 2.812-2.394 6.25-0.8117 3.438-3.611 14.35-6.221 24.25s-5.095 19.58-5.524 21.5-3.066 11.59-5.861 21.47c-2.795 9.884-5.082 18.77-5.082 19.75 0 1.614 1.206 1.779 13 1.779h13zm177.2 14.46c5.863-1.628 8.084-5.667 8.608-15.65 0.8493-16.18-3.405-20.72-18.84-20.11l-7.479 0.2984-0.2752 16.96c-0.1513 9.33-0.0529 17.54 0.2186 18.25 0.6099 1.589 12.34 1.752 17.76 0.246zm-19.01-125.2c-0.8776-0.8776-1.2-8.914-1.2-29.91v-28.71l-14.65-13.94c-8.87-8.444-14.37-14.39-13.94-15.09 1.042-1.685 134.7-1.629 136.4 0.057 0.8958 0.8958 1.2 12 1.2 43.8s-0.3042 42.9-1.2 43.8c-0.9026 0.9026-14.11 1.2-53.3 1.2s-52.4-0.2974-53.3-1.2zm145 0c-0.8958-0.8958-1.2-12-1.2-43.8s0.3042-42.9 1.2-43.8c0.903-0.903 14.26-1.2 53.96-1.2 51.14 0 52.8 0.0594 53.8 1.934 1.116 2.085 1.52 83.64 0.4282 86.48-0.543 1.415-6.217 1.582-53.8 1.582-40.04 0-53.49-0.2968-54.39-1.2zm146 0.3691c-0.9895-0.6281-1.205-10.25-1-44.73l0.2606-43.93 67.94-0.257c47.41-0.1794 68.26 0.0675 69 0.8169 0.7466 0.7586 0.029 1.974-2.443 4.139-1.925 1.686-8.562 8.026-14.75 14.09l-11.25 11.03v28.64c0 20.94-0.3225 28.97-1.2 29.84-1.394 1.394-104.4 1.75-106.6 0.3691z" style="fill: currentColor; color: inherit"/></g></g></svg>`;
    const logo = new UI.SvgView({ width: 96, height: 96 }).setSvg(logoSvg).setStyle({ color: "var(--ui-color-text)" });

    const titleStack = new UI.VDiv({ gap: 0 }).add(
        new UI.Heading("Control Launcher", { level: 2 }).setStyle({ fontSize: "1.6em", margin: "0" }),
        new UI.HDiv().add(
            new UI.Span(A3CL_NAME_SHORT),
            new UI.HSpacer({gap: "1ch"}),
            new UI.Sup("v" + A3CL_VERSION),
        ).setStyle({ fontSize: "0.65em", color: "var(--ui-color-text-muted)" }),
        new UI.HDiv().add(
            new UI.Span(UI.UI_KIT_NAME),
            new UI.HSpacer({gap: "1ch"}),
            new UI.Sup("v" + UI.UI_KIT_VERSION),
        ).setStyle({ fontSize: "0.65em", color: "var(--ui-color-text-muted)" })
    );
    top_banner.add(new UI.HSpacer({gap: "0.1em"}), logo, titleStack, new UI.HSpacer());
}
/* this is now the main layout thingy */
middle_banner.setStyle({ flex: "1", overflow: "auto" });

/* setup navigation tabs */
{
    // Define pages/tabs
    const pages = [
        { id: "dashboard", label: "Dashboard", content: createDashboardContent },
        { id: "server", label: "Server Settings", content: createServerContent },
        { id: "mods", label: "Mods", content: createModsContent },
        { id: "logs", label: "Logs", content: createLogsContent },
    ];

    let currentPage = pages[0];
    let currentButton = null;
    let firstButton = null;
    const pageContainers = {};

    // Create page containers upfront
    pages.forEach(page => {
        const container = new UI.VDiv();
        container.add(page.content());
        container.hide();
        main_display.add(container);
        pageContainers[page.id] = { container, button: null };
    });

    // Function to show a specific page
    const showPage = (pageId) => {
        // Hide all pages
        pages.forEach(page => {
            if (pageContainers[page.id] && pageContainers[page.id].container) {
                pageContainers[page.id].container.hide();
            }
        });
        
        // Show the selected page
        if (pageContainers[pageId] && pageContainers[pageId].container) {
            pageContainers[pageId].container.show();
        }
    };

    // Create navigation buttons
    pages.forEach((page, index) => {
        const btn = new UI.Button(page.label);
        btn.on("click", () => {
            // Remove active style from previous button
            if (currentButton && currentButton.element) {
                currentButton.element.style.backgroundColor = "";
                currentButton.element.style.opacity = "";
            }
            
            // Update current page and button
            currentPage = page;
            currentButton = btn;
            
            // Highlight active button
            if (btn && btn.element) {
                btn.element.style.backgroundColor = "var(--ui-color-control-active, #444)";
                btn.element.style.opacity = "1";
            }
            
            // Show the page
            showPage(page.id);
        });
        btn.setStyle({ 
            width: "100%", 
            textAlign: "left",
            padding: "12px",
            borderRadius: "0",
            border: "none",
            margin: "1px 0px 0px",
            cursor: "pointer",
            transition: "background-color 0.2s"
        });
        left_navigation.add(btn);
        pageContainers[page.id].button = btn;
        
        // Store reference to first button
        if (index === 0) {
            firstButton = btn;
        }
    });

    // Initialize with first page and highlight first button
    if (firstButton && firstButton.element) {
        currentButton = pages[0].__button = firstButton;
        currentButton.element.style.backgroundColor = "var(--ui-color-control-active, #444)";
        showPage(pages[0].id);
    }
}


/* handle the bottom banner */
{
    const disclaimerText = "This software is provided as-is without warranty. Use at your own risk.";
    bottom_banner.setStyle({ borderTop: "1px solid var(--ui-color-border)", paddingTop: "4px" });
    bottom_banner.add(
        new UI.HSpacer({gap: "0.1em"}),
        new UI.Span(disclaimerText).setStyle({ 
            fontSize: "0.8em", 
            color: "var(--ui-color-text-muted)",
            textAlign: "center",
            padding: "8px 0"
        })
    );
}


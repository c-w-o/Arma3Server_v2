# Arma 3 Control Launcher (A3CL)

A3CL is a modern web-based control system for managing Arma 3 dedicated servers. It provides a comprehensive web UI for configuration management, mission orchestration, mod updates, server monitoring, and player management.

## Overview

The launcher consists of two main components:
- **Backend API**: FastAPI-based REST API managing server configurations, missions, mods, and server processes
- **Web UI**: Browser-based interface built with a custom UI framework for intuitive server management

## Key Features

### Web-Based Management
- **Configurations Tab**: Create and manage server configurations with base/override architecture
- **Missions Tab**: Upload and manage missions, check mod compatibility, update workshop content
- **Dashboard**: Quick access to server status and mission selection
- **Mods Tab**: Browse, search, and manage installed Workshop mods
- **Monitoring**: Real-time server status and performance metrics
- **Logs Tab**: View and filter server logs in real-time
- **Jobs Tab**: Track background tasks and operations
- **Players Tab**: Manage player whitelist and permissions
- **Settings**: Configure launcher behavior and credentials

### Server Management
- Automated Arma 3 server startup with configurable mods and parameters
- Headless client orchestration with independent logging
- Steam Workshop integration via SteamCMD with automatic retries and rate limiting
- DLC/Creator DLC support (Contact, CSLA, Global Mobilization, Western Sahara, SOG, Spearhead 1944, Reaction Forces, Expeditionary Forces)
- Configuration inheritance system with base defaults and per-config overrides
- Mission presets with mod compatibility validation

## Project Structure

```
launcher/
├── launcher.py              # CLI entry point
├── example.json             # Example server configuration
├── server_schema.json       # JSON schema for validation
├── arma_launcher/           # Core Python modules
│   ├── api.py              # FastAPI REST API
│   ├── orchestrator.py     # Server process management
│   ├── content_manager.py  # Workshop content handling
│   ├── steamcmd.py         # SteamCMD wrapper
│   ├── models.py           # Pydantic data models
│   ├── config_loader.py    # Configuration system
│   └── ...
└── web/                     # Web UI
    └── app/
        ├── index.html      # Main HTML entry
        ├── app.js          # Application setup and routing
        ├── dashboard.js    # Dashboard tab
        ├── configurations.js  # Configurations tab
        ├── missions.js     # Missions tab
        ├── mods.js         # Mods tab
        ├── logs.js         # Logs tab
        ├── monitoring.js   # Monitoring tab
        ├── players.js      # Players tab
        ├── jobs.js         # Jobs tab
        ├── settings.js     # Settings tab
        └── api/
            └── client.js   # API client wrapper
```

## Web UI Tabs

### Configurations Tab

The **Configurations** tab is the central hub for managing server configurations. It uses a base/override architecture that allows you to define common settings once and override them per configuration.

#### Key Concepts

**Base Configuration (Basis)**
- The foundation containing default settings shared across all configurations
- Includes default mod lists, DLC selections, and server parameters
- Can be edited independently to update all configurations at once

**Configuration Overrides**
- Individual server configs that inherit from base and apply specific overrides
- Can add, remove, or replace mods in any category
- Override DLC selection, server parameters, and network settings
- Each configuration gets its own `.json` file in the configs directory

**Configuration Variants** (Advanced)
- Temporary configurations based on existing configs
- Used for testing mod combinations without modifying the base config
- Can be created from the API but are not persistent

#### User Interface

The Configurations tab features a **4-tab layout**:

##### 1. Basis Tab
Displays the base configuration (defaults) that all configurations inherit from.

**Sections:**
- **Description**: Optional text describing the base configuration
- **DLCs**: List of installed DLCs/Creator DLCs
- **Mods**: Table showing mod counts by category:
  - Server Mods (server-side only)
  - Base Mods (required by clients and server)
  - Client Mods (optional client-side)
  - Maps (terrain/world mods)
  - Mission Mods (mission-specific content)
  
**Click on any category row** to expand and see individual mods with:
- Mod name
- Workshop ID
- Steam Workshop link (🔗 icon)

##### 2. Overrides Tab
Shows configuration-specific overrides applied on top of the base.

**Override Types:**
- **Added Mods**: Mods added to specific categories (shown with ➕)
- **Removed Mods**: Mods removed from base (shown with ➖)
- **Replace**: Complete replacement of a category (shown with ⚠️ REPLACE)

**Special Fields:**
- **Description**: Config-specific description
- **DLC Override**: If different from base DLC selection
- **Server Parameters**: Network settings (hostname, port, password, etc.)

##### 3. Merged Tab
Displays the final computed configuration after applying all overrides to the base.

**What you see:**
- The actual configuration that will be used when starting the server
- All mod categories with resolved conflicts
- Final DLC selection
- Complete server parameters

**Features:**
- **Export Functions**:
  - 📥 **Download Preset HTML**: Download an interactive HTML file containing the mod list with Steam Workshop links and checkboxes (for manual mod installation)
  - 📋 **Copy Launch Parameters**: Copy Arma 3 launch parameters to clipboard (for local testing)
- **Preview Validation**: Shows any conflicts or warnings

##### 4. Edit Tab
Interactive editor for modifying the current configuration (base or override).

**DLC Selection:**
- Visual radio button grid for selecting one DLC/Creator DLC:
  - Keine (None)
  - Contact
  - CSLA Iron Curtain
  - Global Mobilization
  - Western Sahara
  - S.O.G. Prairie Fire
  - Spearhead 1944
  - Reaction Forces
  - Expeditionary Forces
- Note: Contact is mutually exclusive with other Creator DLCs (automatic branch switching)

**Mod Categories (5 sections):**

Each category has:
1. **Mod List Table**:
   - Shows currently configured mods
   - Checkbox for each mod to mark for deletion (only in config overrides)
   - Name, ID, and Steam link
   - Visual indicators:
     - ✓ Installed locally
     - 🌐 From Steam Workshop
     - 📁 Local mod
     - ⚠️ Error/not found

2. **Add Mods Interface**:
   - **Text Area**: Paste mod IDs or Steam Workshop URLs (one per line)
     - Accepts: `450814997`, `https://steamcommunity.com/sharedfiles/filedetails/?id=450814997`
   - **Resolve Button**: Fetch mod names from Steam API
     - Shows preview of mods to be added
     - Displays mod name, ID, and source (Steam/local)
   - **Add Mods Button**: Add resolved mods to the category

**Categories:**
- **Server Mods**: Mods only loaded on server (e.g., admin tools, server-side scripts)
- **Base Mods**: Required mods for all clients (e.g., CBA_A3, RHS)
- **Client Mods**: Optional client-side mods (UI enhancements, graphics)
- **Maps**: Terrain and world mods
- **Mission Mods**: Mission-specific content

**Save/Cancel:**
- **Save Button**: Persist changes to the configuration file
- **Cancel Button**: Discard changes and reload from disk

#### Workflows

**Creating a New Configuration:**
1. Click **➕ Neu** button in the dropdown area
2. Enter configuration name (no slashes)
3. Enter optional description
4. New configuration is created with base defaults
5. Switch to **Edit** tab to customize
6. Add/remove mods as needed
7. Select DLC if required
8. Click **Save**

**Editing Base Configuration:**
1. Select **"─── Basis ───"** from dropdown
2. Switch to **Edit** tab
3. Modify DLCs and mod categories
4. Click **Save**
5. All configurations automatically inherit changes (unless overridden)

**Editing Configuration Override:**
1. Select configuration from dropdown
2. Switch to **Edit** tab
3. Changes are saved as overrides (not affecting base)
4. Can remove base mods by checking deletion checkbox
5. Can add new mods via Add Mods interface
6. Click **Save** to persist

**Adding Mods:**
1. In **Edit** tab, scroll to desired category
2. Paste Workshop IDs or URLs in text area (one per line):
   ```
   450814997
   https://steamcommunity.com/sharedfiles/filedetails/?id=843577117
   463939057
   ```
3. Click **Resolve** to fetch mod names from Steam
4. Review resolved mods (name and ID shown)
5. Click **Add Mods** to add them to configuration
6. Repeat for other categories as needed
7. Click **Save** at bottom of page

**Removing Mods (Config Override Only):**
1. Select a configuration (not base) from dropdown
2. Switch to **Edit** tab
3. Check the checkbox next to mods you want to remove
4. Click **Save**
5. Mods are added to "removed" list in override

**Exporting Configurations:**
1. Select configuration and view **Merged** tab
2. **For HTML Preset**:
   - Click **📥 Download Preset HTML**
   - Save the `.html` file
   - Open in browser to see interactive mod list with Steam links
   - Share with players for manual mod installation
3. **For Launch Parameters**:
   - Click **📋 Copy Launch Parameters**
   - Paste into Arma 3 launcher or batch script
   - Used for local testing/development

#### Technical Details

**Configuration Files:**
- Base: `configs/_defaults.json` (special file containing defaults)
- Configs: `configs/{name}.json` (one file per configuration)
- Format: JSON with optional fields (description, dlcs, workshop overrides, parameters)

**Mod Resolution:**
- Mods are resolved via Steam Web API when adding
- Local mods (in `@modname` folders) are detected automatically
- Workshop mods are downloaded via SteamCMD on server start
- Metadata is cached to avoid repeated API calls

**Inheritance Rules:**
- Each category can have: `added`, `removed`, or `replace` arrays
- `replace` completely overrides the base category
- `added` appends mods to base category
- `removed` filters out specific mods from base
- Higher priority categories (serverMods) shown first to avoid duplicates in display

**Validation:**
- Configuration names must not contain slashes
- DLC selection validated against known DLC list
- Mod IDs validated (numeric Workshop IDs or local paths)
- JSON schema validation on save
- Duplicate mod IDs within a category are prevented

---

### Dashboard Tab

*(To be documented)*

### Missions Tab

The **Missions** tab allows you to manage mission files (.pbo), check mod compatibility, and track mod updates for your server.

#### What it does

- **Select a configuration** to manage missions and updates for that specific config.
- **Upload mission files** (.pbo or .zip) with optional descriptions.
- **Check for mod updates** in uploaded missions and apply them selectively.
- **View all uploaded missions** with compatibility status and upload dates.
- **Edit mission metadata** (description only; mod lists are informational and stored separately).

#### Sections

**1. Configuration Selection**
- Dropdown selector that enables all sections below.
- Each mission is tied to a specific configuration, allowing different missions for different configs.

**2. Mod Updates**
- **🔍 Check for Updates**: Scans all Workshop mods in the configuration for available updates.
- **Select All / Select None**: Quickly select/deselect mods to update.
- **⬇ Update starten**: Downloads and applies selected mod updates sequentially.
- **Progress bar**: Shows current mod name and update progress (e.g., "Update: ModName (3/7)").

#### Key Rules for Unique Missions

**Mission Uniqueness** is based on **file content (SHA256 hash)**, not file name:
- ✅ You **can** upload multiple missions with the **same name** to the same config (they get unique IDs).
- ❌ You **cannot** upload a mission with **identical content** twice (detected by file hash).
  - If duplicate content is detected, the upload is rejected with a message showing the existing mission's name and ID.
- Missions are always timestamped with upload date/time for easy identification.

#### Sections Detail

**Mission Upload**
- **Select file**: Choose a .pbo or .zip mission file.
- **Mission name** (optional): Provide a custom name; if not given, the filename (without extension) is used.
- **Description** (optional): Add notes about the mission (e.g., "PvP with custom gear" or "Coop 6-player").
- **Upload button**: Uploads the file and registers it to the selected configuration.

**Mission List & Compatibility**
- Each mission card shows:
  - **Name** and **Description**
  - **Status icon**: ✓ (green) if all required mods are present, ⚠ (orange) if mods are missing.
  - **Mod count**: Number of required + optional mods (for reference/documentation only).
  - **Upload date**: When the mission was uploaded (e.g., "2 Feb 2026, 14:23").
  - **Config mismatch warning**: ⚠️ if the configuration has changed since the mission was uploaded.
- Click a mission card to view or edit its metadata.

**Mission Details & Metadata Editor**
- Displays the selected mission's full information.
- **Description editor**: Edit the mission description and save changes.
- Changes are stored in the missions index and persist across server restarts.

#### Typical workflow

1. **Select a configuration** from the dropdown.
2. **Upload a mission** file (.pbo) with an optional name and description.
   - If the file already exists (identical hash), the upload is rejected.
3. **Check for mod updates** by clicking "🔍 Aktualität prüfen".
4. **Select which mods to update** (outdated mods are pre-selected).
5. **Start the update** to download all selected mod versions.
6. **View uploaded missions** in the list below; click to see full details and edit descriptions.

#### Notes

- **Mission metadata** (name, description, mod references) is stored separately from the `.pbo` file in `missions.json`.
- **Mod compatibility** is checked against the configuration's Workshop mods; it is informational only.
- **Upload dates** help you track when missions were added; useful for audit trails and version management.
- If a mission becomes incompatible due to configuration changes, you'll see a warning. You can update required mods and refresh to resolve it.

### Mods Tab

The **Mods** tab is a read-only overview of the Workshop content assigned to a configuration, plus tools to export or sanitize HTML mod presets for players.

#### What it does

- **Select a configuration** from the dropdown to view its Workshop mods, maps, and DLCs.
- **Open any mod in Steam** by clicking a row in the tables.
- **Export HTML mod presets** for sharing with players.
- **Upload and sanitize** an existing HTML preset (removes unknown/invalid entries and normalizes IDs).

#### Sections

**Configuration Selector**
- Dropdown at the top that drives all tables below.
- Changing the selection updates the mod lists and enables preset export.

**HTML Preset Import/Export**
- **⬇ Download All Mods (ohne Server)**: Exports a preset containing all non-server mods.
- **⬇ Download Mods & Maps**: Exports a preset containing mods + maps only.
- **Upload & Bereinigen**: Upload a preset `.html` file, sanitize it, and download a cleaned version.

**Mods & Maps**
- Combined list of **mods** and **maps** from the selected configuration.
- Each row shows name and Workshop ID; clicking opens the Steam Workshop page.

**Client Mods**
- Optional mods intended for client-side use only.

**Server Mods**
- Server-only mods (e.g., server tools or admin utilities).

**DLCs**
- List of DLCs enabled for the configuration (or “No DLCs” if none are set).

#### Typical workflow

1. Select a configuration.
2. Review **Mods & Maps**, **Client Mods**, and **Server Mods**.
3. Click a row to open the Workshop page and share links if needed.
4. Use **Download** buttons to generate HTML presets for players.
5. If a player sends a preset back, **Upload & Bereinigen** to sanitize it.

### Logs Tab

*(To be documented)*

### Monitoring Tab

*(To be documented)*

### Players Tab

*(To be documented)*

### Jobs Tab

*(To be documented)*

### Settings Tab

*(To be documented)*

---

## Installation & Deployment

### Docker Deployment (Recommended)

A Dockerfile is included for containerized deployment. Typical run (adjust volumes and ports):

- Map Arma install/mod folders and config:
  - /arma3 – game root and logs
  - /var/run/share – credential JSON if used
- Example:
```bash
docker run -d \
  -v /path/to/arma:/arma3 \
  -v /path/to/creds:/var/run/share \
  -p 2302:2302/udp \
  --env ARMA_CONFIG_JSON=/var/run/share/steam_credentials.json \
  --name arma_server \
  <image-name>
```
Inside the container the launcher will place logs in `/arma3/logs` by default.

## Troubleshooting & tips
- "result 26 (Request revoked)" usually indicates Steam rejected the session or rate-limiting. Common mitigations:
  - Avoid concurrent SteamCMD logins (use `HC_START_DELAY` and the launcher’s SteamCMD locking).
  - Ensure Steam Guard / 2FA is satisfied for the account used; prefer an account without 2FA for automated SteamCMD downloads or use a guard-aware workflow.
  - Increase SteamCMD retries and backoff in config (`sleep_seconds`, `retries`).
  - Check container/system clock — large clock skew can affect Steam auth.
- If headless clients connect too rapidly, increase `HC_START_DELAY` to 2–5s.
- Use the separate warning log file (configured patterns) to reduce noise in main logs.
- Ensure the server has proper file permissions for symlink creation and writing logs.

## Extending / contributing
- Add new `separate_patterns` in `server.py` to route additional noisy lines out of main logs.
- Improve SteamCMD handling by adding better parsing for Steam responses or adding refresh token flows.
- Add unit tests for `mods.py` and `steam.py` runner logic (steam runner is ideal for mocking).
- Follow project coding style and run linter before submitting PRs.

## License
See LICENSE file in repository root.

## Contact / support
Open an issue in this repository with logs (server and steamcmd output) and configuration snippet (redact credentials) for faster assistance.
# Arma3Server_v2

Arma3Server_v2 is a lightweight, Docker-friendly Arma 3 dedicated server launcher.  
It automates Arma 3 server startup, headless client orchestration, Steam Workshop mod downloads (via SteamCMD), optional DLC/install handling, logging, and resilient SteamCMD retries and backoff. The project is intended for run-in-container or host-based automated server deployments.

## Key features
- Build and launch Arma 3 dedicated server command line with configurable mods and server mods.
- Orchestrate configurable number of headless clients (HCs), each with their own logger and log files.
- Steam Workshop integration via SteamCMD with retries, backoff and transient error detection (e.g. "result 26" / "Request revoked").
- Optional DLC/app install via SteamCMD (config-driven).
- Streaming logs from server and HCs into separate files and logger streams; configurable filters and pattern-based split logs.
- Mod linking and safe operations: symlink creation, normalization, minimal verification.
- Docker-friendly layout and sensible defaults for log and config paths.

## Project layout
- `launcher/launcher.py` – CLI entry and orchestration.
- `launcher/example.json` – example server profile / config (server.json schema reference).
- `launcher/server_schema.json` – JSON schema used to validate server profiles.
- `launcher/debug_mods.py` – helper utilities for mod debugging.
- `launcher/arma_launcher/` – core implementation:
  - `server.py` – main ServerLauncher: builds launch command, starts server and HCs, streams logs.
  - `steam.py` – SteamCMD wrapper: downloads mods, installs apps/DLCs, retry logic, output parsing.
  - `mods.py` – ModManager: resolves mod lists, links mods into server directory, copies keys.
  - `config.py` – configuration loader: environment + optional JSON profile, defaults and overrides.
  - `log.py` – centralized logging setup used by all modules.
  - `config_generator.py` – optional helper to create runtime configs (used by HC/server configs).
  - `setup.py` – packaging / entry metadata (if used as library).

## How it works (high level)
1. Configuration is loaded from environment variables and optional JSON profile (defaults/active).
2. Steam credentials can be provided via a JSON file path (default `/var/run/share/steam_credentials.json`) or environment variables.
3. The `SteamCMD` helper ensures required DLCs/apps are present (if configured) and downloads Workshop mods into a temporary folder using SteamCMD with resilient retry/backoff.
4. `ModManager` creates safe symlinks from the workshop content to the server mod folders and copies server keys as needed.
5. `ServerLauncher` builds the Arma 3 process command line:
   - Adds `-mod` and `-serverMod` parameters by scanning mod directories for `@mod` folders.
   - Adds base config and parameter config files when present.
   - Supports file patching config toggles and other launch-time flags.
6. The Arma server process is spawned with live pipes; separate threads stream stdout/stderr through `stream_reader` into Python loggers and tile files. `stream_reader` supports filters and `separate_patterns` to route noisy or known warning lines to a dedicated file.
7. Headless clients are started and streamed independently; each HC gets its own logger and log files. An optional start delay (`HC_START_DELAY`) serializes HC startups to reduce rate and race conditions.
8. SteamCMD invocations are guarded with pattern detection to treat certain outputs as transient (rate limits, "result 26", "Request revoked"), which triggers kill-and-retry behavior with exponential backoff. Optionally a lock-file can be used to serialize SteamCMD access across parallel launcher processes.

## Configuration
Configuration may be supplied via environment variables or a JSON profile (see `launcher/example.json`). Important variables:
- ARMA_BINARY – path to arma3 server binary (default: `/arma3/arma3server_x64`)
- ARMA_CONFIG_JSON – path to steam credential JSON (default used in container)
- HC_START_DELAY – seconds to wait between headless client starts (default `1`)
- LOG_LEVEL – logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- LOG_JSON – set `"true"` to use JSON formatted logs
- STEAM_USER / STEAM_PASSWORD – fallback credentials if no credential JSON provided
- headless_clients – number of headless clients to spawn (configured in JSON profile)
- dlcs – optional list of appids (strings or objects) to ensure installed via SteamCMD
- mods / servermods – mod lists or directories as configured in profile

Example JSON (snippet):
```json
{
  "defaults": {
    "dlcs": ["234586", {"appid":"654321"}]
  },
  "active": "production",
  "profiles": {
    "production": {
      "headless_clients": 2,
      "mods": ["@cba_a3", "@rhsusf"],
      "servermods": ["@cba_a3"]
    }
  }
}
```

## Running (Docker)
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
from __future__ import annotations
from pathlib import Path
from .models import MergedConfig
from .logging_setup import get_logger

log = get_logger("arma.launcher.cfg")

def generate_profile_cfg(cfg: MergedConfig, profiles_dir: Path, profile_name: str) -> Path:
    """
    Creates <profiles_dir>/<profile_name>.Arma3Profile with Custom difficulty preset.
    This is the classic place where "difficulty=custom" actually becomes real.
    """
    profiles_dir.mkdir(parents=True, exist_ok=True)
    out = profiles_dir / f"{profile_name}.Arma3Profile"

    # Minimal-but-useful Custom preset (extend later if you want full legacy parity)
    text = r'''
version=2;
difficulty="Custom";

class DifficultyPresets
{
    class CustomDifficulty
    {
        class Options
        {
            // 0/1 toggles – keep it conservative (server-friendly)
            groupIndicators=0;
            friendlyTags=0;
            enemyTags=0;
            detectedMines=0;
            commands=0;
            waypoints=0;
            weaponInfo=1;
            stanceIndicator=0;
            staminaBar=1;
            weaponCrosshair=0;
            visionAid=0;
            thirdPersonView=0;
            cameraShake=1;
            scoreTable=1;
            deathMessages=0;
            vonID=1;
            mapContent=0;
            autoReport=0;
            multipleSaves=0;
        };

        // AI tuning – defaults are OK; keep explicit so "custom" is truly custom
        aiLevelPreset=3;
    };
};
'''.lstrip()

    out.write_text(text, encoding="utf-8")
    log.info("Generated profile cfg: %s", out)
    return out


def generate_server_cfg(cfg: MergedConfig, out_path: Path) -> None:
    s = cfg.server
    lines = [
        f'hostname = "{s.hostname}";',
        f'password = "{s.password}";',
        f'passwordAdmin = "{s.password_admin}";',
        f'maxPlayers = {s.max_players};',
        f'verifySignatures = {s.verify_signatures};',
        f'BattlEye = {1 if s.battleye else 0};',
        f'kickDuplicate = {1 if s.kick_duplicate else 0};',
        f'equalModRequired = {1 if s.equal_mod_required else 0};',
        f'allowedFilePatching = {int(s.allowed_file_patching)};',
        f'timeStampFormat = "{s.time_stamp_format}";',
        f'logFile = "{s.log_file}";',
        f'persistent = {1 if s.persistent else 0};',
        f'steamProtocolMaxDataSize = {s.steamMaxSize};',
        f'disableVoN = {0 if s.disableVoN else 1};',
        f'vonCodec = {s.vonCodec};',
        f'vonCodecQuality = {s.vonCodecQuality};',
        f'forcedDifficulty = "{s.forcedDifficulty}";'
    ]

    if s.headless_clients:
        hc = ", ".join([f'"{x}"' for x in s.headless_clients])
        lines.append(f"headlessClients[] = {{ {hc} }};")
    if s.local_clients:
        lc = ", ".join([f'"{x}"' for x in s.local_clients])
        lines.append(f"localClient[] = {{ {lc} }};")

    if s.motd:
        motd = ", ".join([f'"{m}"' for m in s.motd])
        lines.append(f"motd[] = {{ {motd} }};")
        lines.append(f"motdInterval = {s.motd_interval};")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("Generated server cfg: %s", out_path)

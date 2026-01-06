from __future__ import annotations
from pathlib import Path
from .models import MergedConfig
from .logging_setup import get_logger

log = get_logger("arma.launcher.cfg")

def _read_optional_template(out_path: Path, filename: str) -> str | None:
    tmpl = out_path.parent / filename
    if tmpl.exists():
        try:
            return tmpl.read_text(encoding="utf-8")
        except Exception as e:
            log.warning("Failed to read template %s (%s). Falling back to generated config.", tmpl, e)
    return None


def _render_template(template: str, mapping: dict[str, str]) -> str:
    out = template
    for k, v in mapping.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def _q(s: str) -> str:
    return str(s).replace('"', '\\"')



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

def generate_server_cfg(cfg: MergedConfig, out_path: Path) -> Path:
    """
    Generates the Arma 3 server.cfg (generated_a3server.cfg).

    Optional template support:
      <out_path.parent>/templates/a3server.cfg.tmpl

    Placeholders:
      {{hostname}}, {{password}}, {{password_admin}}, {{server_command_password}},
      {{admins_array}}, {{max_players}}, {{verify_signatures}}, {{battleye}},
      {{kick_duplicate}}, {{equal_mod_required}}, {{allowed_file_patching}},
      {{time_stamp_format}}, {{log_file}}, {{persistent}}
    """
    s = cfg.server

    tmpl = _read_optional_template(out_path, "a3server.cfg.tmpl")
    if tmpl:
        log.info("Generating config from template")
        admins_array = ", ".join(
            [f'"{a.steamid}"' for a in (getattr(s, "admins", []) or []) if getattr(a, "steamid", "")]
        )
        mapping = {
            "hostname": _q(s.hostname),
            "password": _q(s.password),
            "password_admin": _q(getattr(s, "password_admin", "")),
            "server_command_password": _q(getattr(s, "server_command_password", "")),
            "admins_array": admins_array,
            "max_players": str(s.max_players),
            "verify_signatures": str(s.verify_signatures),
            "battleye": "1" if s.battleye else "0",
            "kick_duplicate": "1" if s.kick_duplicate else "0",
            "equal_mod_required": "1" if s.equal_mod_required else "0",
            "allowed_file_patching": str(int(s.allowed_file_patching)),
            "time_stamp_format": _q(s.time_stamp_format),
            "log_file": _q(s.log_file),
            "persistent": "1" if s.persistent else "0",
            "steamProtocolMaxDataSize": str(int(s.steamMaxSize)),
            "disableVoN": "0" if s.disableVoN else "1",
            "vonCodec": str(int(s.vonCodec)),
            "vonCodecQuality": str(int(s.vonCodecQuality)),
            "forcedDifficulty": _q(s.forcedDifficulty)
        }
                
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(_render_template(tmpl, mapping) + "\n", encoding="utf-8")
        log.info("Generated server cfg (template): %s", out_path) 
        return out_path
    log.info("Generating config from scratch")
    lines = [
        f'hostname = "{s.hostname}";',
        f'password = "{s.password}";',
        f'passwordAdmin = "{s.password_admin}";',
    ]

    scp = getattr(s, "server_command_password", "")
    if scp:
        lines.append(f'serverCommandPassword = "{scp}";')

    if getattr(s, "admins", None):
        admins = ", ".join([f'"{a.steamid}"' for a in s.admins if getattr(a, "steamid", "")])
        if admins:
            lines.append(f"admins[] = {{ {admins} }};")

    lines += [
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
        f'vonCodecQuality = {s.vonCodecQuality};'
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
    return out_path
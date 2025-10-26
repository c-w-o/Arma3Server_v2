import json
import os
import sys
import logging
from jsonschema import validate, ValidationError
from pathlib import Path
from arma_launcher.log import get_logger

logger = get_logger()
# Try to use json5 (lenient JSON with comments/trailing commas)
try:
    import json5
except ModuleNotFoundError:
    json5 = None

# Default schema location: next to launcher.py (one level above this package)
DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "server_schema.json"


def load_json(path: Path):
    """Load JSON file; prefer json5 if available to allow comments/trailing commas."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        if json5:
            return json5.load(f)
        return json.load(f)


def validate_config(config, schema):
    try:
        validate(instance=config, schema=schema)
        return True, None
    except ValidationError as e:
        location = "/".join(str(p) for p in getattr(e, "path", []))
        return False, f"JSON Schema Validation Error: {str(e)} (at {location})"


def merge_defaults(config):
    """Merge global defaults with the active configuration"""
    defaults = config.get("defaults", {})
    active_name = config["config-name"]
    active_cfg = config["configs"][active_name]

    merged = defaults.copy()
    merged.update(active_cfg)
    return merged


def generate_a3server_cfg(merged):
    """Create textual A3 server.cfg"""
    cfg = []

    # Basic settings
    cfg.append(f'hostname = "{merged.get("hostname", "Arma 3 Server")}";')
    cfg.append(f'password = "{merged.get("serverPassword", "")}";')
    cfg.append(f'passwordAdmin = "{merged.get("adminPassword", "")}";')
    cfg.append(f'serverCommandPassword = "{merged.get("serverCommandPassword", "")}";')
    cfg.append(f'maxPlayers = {merged.get("maxPlayers", 32)};')
    cfg.append("persistent = 1;")
    cfg.append("verifySignatures = 1;")
    cfg.append("voteThreshold = 0.33;")
    cfg.append("logFile = \"logs/server_console_%Y-%m-%d.log\";")
    cfg.append("timeStampFormat = \"full\";")
    cfg.append("BattlEye = 0;")
    cfg.append("kickDuplicate = 1;")
    cfg.append("disableVoN = 1;")
    cfg.append("vonCodec = 1;")
    cfg.append("vonCodecQuality = 25;")
    cfg.append("disconnectTimeout = 10;")
    cfg.append("maxDesync = 120;")
    cfg.append("maxPing = 300;")
    cfg.append("maxPacketLoss = 30;")
    
    # Admin Steam IDs (falls angegeben)
    admins = merged.get("admins", [])
    if admins:
        # Build multiline admins[] block:
        lines = []
        for i, a in enumerate(admins):
            # allow either plain steamid strings or dicts like {"name": "...", "steamid": "..."
            if isinstance(a, dict):
                sid = a.get("steamid") or a.get("id") or a.get("steam_id")
                name = a.get("name")
            else:
                sid = str(a)
                name = None
            if not sid:
                # skip invalid entries
                continue
            comma = "," if i != len(admins) - 1 else ""
            comment = f" // {name}" if name else ""
            lines.append(f'    "{sid}"{comma}{comment}')
        cfg.append("admins[] = {")
        cfg.extend(lines)
        cfg.append("};")

    # Headless clients
    hc_count = merged.get("numHeadless", 0)
    if hc_count > 0:
        cfg.append('headlessClients[] = {"127.0.0.1"};')
        cfg.append('localClient[] = {"127.0.0.1"};')

    # Optional mission list
    missions = merged.get("missions", [])
    if missions:
        cfg.append("\nclass Missions\n{")
        for i, m in enumerate(missions, start=1):
            cfg.append(f"    class Mission_{i}")
            cfg.append("    {")
            cfg.append(f'        template = "{m.get("name", "")}";')
            diff = m.get("difficulty", merged.get("difficulty", "Custom"))
            cfg.append(f'        difficulty = "{diff}";')
            cfg.append("    };")
        cfg.append("};")

    return "\n".join(cfg)


def generate_for_config(cfg, schema_path: Path = None, output_name: str = "generated_a3server.cfg") -> None:
    """
    Generate the a3server.cfg using an ArmaConfig instance.
    - cfg: ArmaConfig instance (provides cfg.config_dir)
    - schema_path: optional Path to schema; defaults to cfg.config_dir / "server_schema.json"
    - output_name: filename to write inside cfg.config_dir
    Raises exceptions on fatal errors.
    """
    logger = get_logger().getChild("config_generator")
    config_dir = Path(cfg.config_dir)
    server_json = config_dir / "server.json"
    # prefer explicit schema_path, otherwise use the shipped schema next to launcher.py
    schema_file = Path(schema_path) if schema_path else DEFAULT_SCHEMA_PATH
    output_cfg = config_dir / output_name

    logger.info("Generating a3server.cfg from %s (schema=%s)", server_json, schema_file)

    # load & validate
    config = load_json(server_json)
    schema = load_json(schema_file)

    ok, error = validate_config(config, schema)
    if not ok:
        logger.error("Validation failed: %s", error)
        raise ValueError(error)

    if "config-name" not in config:
        raise ValueError("Missing 'config-name' in server.json")
    if "configs" not in config or not isinstance(config["configs"], dict):
        raise ValueError("Missing/invalid 'configs' object in server.json")
    if config["config-name"] not in config["configs"]:
        raise ValueError(f"Active config '{config['config-name']}' not found in 'configs'")

    merged = merge_defaults(config)
    cfg_text = generate_a3server_cfg(merged)

    # write output
    output_cfg.parent.mkdir(parents=True, exist_ok=True)
    with open(output_cfg, "w", encoding="utf-8") as fh:
        fh.write(cfg_text)

    logger.info("Wrote %s", output_cfg)


def main():
    logger.info("Validating and generating a3server.cfg...")

    # ensure SCHEMA_FILE falls back to the shipped schema next to launcher.py
    if "SCHEMA_FILE" not in globals():
        SCHEMA_FILE = DEFAULT_SCHEMA_PATH

    try:
        if not os.path.exists(SERVER_JSON):
            logger.error("Missing server JSON: %s", SERVER_JSON)
            raise FileNotFoundError(SERVER_JSON)
        if not os.path.exists(SCHEMA_FILE):
            logger.error("Missing schema JSON: %s", SCHEMA_FILE)
            raise FileNotFoundError(SCHEMA_FILE)

        try:
            config = load_json(SERVER_JSON)
        except Exception as e:
            logger.exception("Failed to parse server JSON '%s': %s", SERVER_JSON, e)
            sys.exit(2)

        try:
            schema = load_json(SCHEMA_FILE)
        except Exception as e:
            logger.exception("Failed to parse schema JSON '%s': %s", SCHEMA_FILE, e)
            sys.exit(3)

        ok, error = validate_config(config, schema)
        if not ok:
            logger.error("Validation failed: %s", error)
            sys.exit(4)

        # Basic structural checks
        if "config-name" not in config:
            logger.error("Missing required field 'config-name' in server.json")
            sys.exit(5)
        if "configs" not in config or not isinstance(config["configs"], dict):
            logger.error("Missing or invalid 'configs' object in server.json")
            sys.exit(6)
        if config["config-name"] not in config["configs"]:
            logger.error("Active config '%s' not found in 'configs'", config["config-name"])
            sys.exit(7)

        merged = merge_defaults(config)
        logger.debug("Merged configuration: %s", merged)

        cfg_text = generate_a3server_cfg(merged)

        try:
            os.makedirs(os.path.dirname(OUTPUT_CFG), exist_ok=True)
            with open(OUTPUT_CFG, "w", encoding="utf-8") as f:
                f.write(cfg_text)
        except PermissionError as e:
            logger.exception("Permission error writing output file '%s': %s", OUTPUT_CFG, e)
            sys.exit(8)
        except OSError as e:
            logger.exception("OS error writing output file '%s': %s", OUTPUT_CFG, e)
            sys.exit(9)

        logger.info("Generated %s for config: %s", OUTPUT_CFG, config["config-name"])
        return 0

    except FileNotFoundError as e:
        logger.exception("Required file not found: %s", e)
        sys.exit(1)
    except ModuleNotFoundError as e:
        logger.exception("Required module missing: %s", e)
        sys.exit(10)
    except Exception as e:  # fallback for unexpected errors
        logger.exception("Unhandled exception: %s", e)
        sys.exit(99)


if __name__ == "__main__":
    main()

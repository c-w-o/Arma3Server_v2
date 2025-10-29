#!/usr/bin/env python3
"""
Arma 3 Dedicated Server Launcher (modular version)
Author: Don & ChatGPT Refactor
"""

import sys
import os
from pathlib import Path
# logger früh initialisieren, damit Module beim Import bereits korrekt loggen
from arma_launcher.log import setup_logger, get_logger

level = os.getenv("LOG_LEVEL", "INFO").upper()
json_format = os.getenv("LOG_JSON", "false").lower() == "true"
setup_logger(level=level, json_format=json_format)
logger = get_logger()

# jetzt die übrigen Module importieren (können während Import loggen)
from arma_launcher.config import ArmaConfig
from arma_launcher.mods import ModManager
from arma_launcher.server import ServerLauncher
from arma_launcher.steam import SteamCMD
from arma_launcher.setup import ArmaSetup
from arma_launcher.config_generator import generate_for_config

def main():
    # --- Initialize logging ---
    # setup_logger wurde bereits oben ausgeführt
    logger.info("=== Starting Arma 3 Dedicated Launcher ===")

    # --- Load environment & JSON config ---
    try:
        config = ArmaConfig.from_env()
    except Exception as e:
        logger.exception(f"Failed to load configuration: {e}")
        sys.exit(1)

    # --- Prepare filesystem and base folders ---
    setup = ArmaSetup(config)
    try:
        setup.prepare_environment()
    except Exception as e:
        logger.exception(f"Environment setup failed: {e}")
        
        sys.exit(1)
    
    # --- Ensure Arma is installed (optional via SteamCMD) ---
    steam = SteamCMD(config)
    arma_binary_env = os.getenv("ARMA_BINARY", "")
    arma_path = Path(arma_binary_env) if arma_binary_env else (config.arma_root / "arma3server_x64")
    if not arma_path.exists():
        if config.skip_install:
            logger.error("Arma binary not found and SKIP_INSTALL=true — cannot continue.")
            sys.exit(1)
        logger.info(f"Arma binary {arma_path} missing — attempting install/update via SteamCMD.")
        if not steam.install_arma(str(config.arma_root)):
            logger.error("Arma installation/update failed — exiting.")
            sys.exit(1)
        logger.info("Arma install/update finished.")
    else:
        logger.info(f"Arma binary present: {arma_path}")
    
    # --- Generate server config from server.json/schema (must exist in config dir now) ---
    try:
        generate_for_config(config)
    except Exception as e:
        logger.exception(f"Generating a3server.cfg failed: {e}")
        sys.exit(1)

    # --- Handle mods and workshop ---
    mods = ModManager(config, steam)
    if not mods.sync():
        logger.error("Mod synchronization failed — exiting.")
        sys.exit(1)

    # --- Launch Arma server ---
    server = ServerLauncher(config, mods)
    try:
        server.start()
    except Exception as e:
        logger.exception(f"Server launch failed: {e}")
        sys.exit(1)

    logger.info("=== Arma 3 Launcher completed successfully ===")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Arma 3 Dedicated Server Launcher (modular version)
Author: Don & ChatGPT Refactor
"""

import sys
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
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

    # Entscheide hier nur, ob eine Installation/Validation nötig ist — führe sie später parallel aus.
    need_install_or_validate = False
    if not arma_path.exists():
        if config.skip_install:
            logger.error("Arma binary not found and SKIP_INSTALL=true — cannot continue.")
            sys.exit(1)
        logger.info(f"Arma binary {arma_path} missing — will attempt install/update via SteamCMD.")
        need_install_or_validate = True
    else:
        logger.info(f"Arma binary present: {arma_path}")
        if config.skip_install:
            logger.info("SKIP_INSTALL=true — skipping validation of existing Arma installation.")
        else:
            logger.info("Will validate Arma installation via SteamCMD (app_update validate).")
            need_install_or_validate = True

    if need_install_or_validate:
        if not steam.install_arma(str(config.arma_root)):
            logger.error("Arma installation/update failed — exiting.")
            sys.exit(1)
        logger.info("Arma install/update finished.")
    
    # --- Generate server config from server.json/schema (must exist in config dir now) ---
    try:
        generate_for_config(config)
    except Exception as e:
        logger.exception(f"Generating a3server.cfg failed: {e}")
        sys.exit(0)

    # --- Handle mods and workshop ---
    mods = ModManager(config, steam)

    # Parallelisiere Mod-Sync und optional Arma-Install/Validate (SteamCMD)
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_sync = ex.submit(mods.sync)
        f_install = ex.submit(steam.install_arma, str(config.arma_root)) if need_install_or_validate else None

        sync_ok = f_sync.result()
        install_ok = True if f_install is None else f_install.result()

    if not sync_ok:
        logger.error("Mod synchronization failed — exiting.")
        sys.exit(1)
    if not install_ok:
        logger.error("Arma installation/validation failed — exiting.")
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

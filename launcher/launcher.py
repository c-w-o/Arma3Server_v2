#!/usr/bin/env python3
"""
Arma 3 Dedicated Server Launcher (modular version)
Author: Don & ChatGPT Refactor
"""

import sys
from arma_launcher.log import setup_logger, get_logger
from arma_launcher.config import ArmaConfig
from arma_launcher.mods import ModManager
from arma_launcher.server import ServerLauncher
from arma_launcher.steam import SteamCMD
from arma_launcher.setup import ArmaSetup
from arma_launcher.config_generator import generate_for_config

def main():
    # --- Initialize logging ---
    setup_logger()  # uses defaults or ENV-controlled options
    logger = get_logger()

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

    # --- Generate server config from server.json/schema (must exist in config dir now) ---
    try:
        generate_for_config(config)
    except Exception as e:
        logger.exception(f"Generating a3server.cfg failed: {e}")
        sys.exit(1)

    # --- Handle mods and workshop ---
    steam = SteamCMD(config)
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

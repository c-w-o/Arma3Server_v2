"""
mods.py — Mod management and linking system for Arma 3 server
--------------------------------------------------------------
Handles mod linking, SteamCMD updates, key copying, and workshop synchronization.
"""

import os
import glob
import shutil
from pathlib import Path
from arma_launcher.log import get_logger

logger = get_logger()


class ModManager:
    def __init__(self, config, steam):
        self.cfg = config
        self.steam = steam
        self.workshop_dir = config.tmp_dir
        self.mods_dir = config.mods_dir
        self.servermods_dir = config.servermods_dir
        self.keys_dir = config.keys_dir

    # ---------------------------------------------------------------------- #
    def sync(self) -> bool:
        """
        Synchronizes mods from JSON configuration and Steam Workshop.
        """
        logger.info("Starting mod synchronization...")

        mods_to_download = []
        for modlist, category in [
            (getattr(self.cfg, "servermods", []), "servermods"),
            (getattr(self.cfg, "mods", []), "mods"),
            (getattr(self.cfg, "maps", []), "maps"),
        ]:
            for name, steamid in modlist:
                if not steamid:
                    logger.debug(f"Skipping non-Steam mod: {name}")
                    continue
                mod_path = self.workshop_dir / steamid
                if not mod_path.exists():
                    logger.info(f"Missing mod {name} ({steamid}) — queued for download.")
                    mods_to_download.append((name, steamid))
                else:
                    logger.debug(f"Mod {name} ({steamid}) already present.")

        # Download missing mods
        for name, steamid in mods_to_download:
            self.steam.download_mod(steamid)

        # Link all mods into Arma directories
        self._link_all_mods()
        logger.info("Mod synchronization complete.")
        return True

    # ---------------------------------------------------------------------- #
    def _link_all_mods(self):
        """Create symbolic links for mods and servermods from workshop."""
        logger.debug("Linking all mods into /arma3/mods and /arma3/servermods...")

        all_mods = []
        for modlist, target_dir in [
            (getattr(self.cfg, "servermods", []), self.servermods_dir),
            (getattr(self.cfg, "mods", []), self.mods_dir),
            (getattr(self.cfg, "maps", []), self.mods_dir),
        ]:
            for name, steamid in modlist:
                if not steamid:
                    continue
                src = self.workshop_dir / steamid
                dst = target_dir / f"@{name}"
                self._safe_link(src, dst)
                self._copy_keys(src, name, steamid)
                all_mods.append(dst)

        logger.info(f"Linked total {len(all_mods)} mods.")

    # ---------------------------------------------------------------------- #
    def _safe_link(self, src: Path, dst: Path):
        """Create symlink if not exists."""
        try:
            if dst.exists() or dst.is_symlink():
                logger.debug(f"Skipping existing mod link: {dst}")
                return
            os.symlink(src, dst)
            logger.info(f"Linked {dst} → {src}")
        except Exception as e:
            logger.error(f"Failed to link {dst} → {src}: {e}")

    # ---------------------------------------------------------------------- #
    def _copy_keys(self, moddir: Path, dispname: str, steamid: str):
        """Copies all .bikey files from a mod to the server's keys folder."""
        keys = glob.glob(str(moddir / "**/*.bikey"), recursive=True)
        if not keys:
            logger.warning(f"No keys found for mod {dispname} ({steamid})")
            return

        for key_file in keys:
            try:
                target = self.keys_dir / f"{steamid}_{Path(key_file).name}"
                shutil.copy2(key_file, target)
                logger.debug(f"Copied key {target}")
            except Exception as e:
                logger.error(f"Failed to copy key {key_file}: {e}")

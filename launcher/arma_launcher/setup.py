"""
setup.py — Environment preparation for the Arma 3 dedicated server
------------------------------------------------------------------
Responsible for cleaning up the Arma root directory, creating required
folders, linking shared configs and DLCs, and ensuring a consistent structure
before mods and server launch.
"""

import os
import shutil
from pathlib import Path
from arma_launcher.log import get_logger

logger = get_logger()


class ArmaSetup:
    def __init__(self, config):
        self.cfg = config
        self.arma_root = config.arma_root
        self.common_share = Path("/var/run/share/arma3/server-common")
        self.this_share = Path("/var/run/share/arma3/this-server")

    # ---------------------------------------------------------------------- #
    def prepare_environment(self):
        """
        Fully prepare the Arma 3 environment:
        - clean previous links/folders
        - recreate required directories
        - symlink shared config/userconfig/logs
        - link DLCs and missions
        """
        logger.info("Preparing Arma 3 server environment...")

        self._cleanup_arma_root()
        self._create_required_dirs()
        self._link_shared_resources()

        logger.info("Environment preparation complete.")

    # ---------------------------------------------------------------------- #
    def _cleanup_arma_root(self):
        """Remove all old links/folders except persistent system dirs."""
        keep = {"steamapps", "battleye", "OCAPLOG", "OCAPTMP"}
        remove_links = []
        remove_dirs = []
        ignore_files = []

        logger.debug(f"Cleaning up {self.arma_root} ...")

        for item in self.arma_root.iterdir():
            if item.name in keep:
                continue
            if item.is_symlink():
                remove_links.append(item)
            elif item.is_dir():
                remove_dirs.append(item)
            else:
                ignore_files.append(item)

        for link in remove_links:
            try:
                link.unlink()
                logger.debug(f"Unlinked: {link}")
            except Exception as e:
                logger.warning(f"Failed to unlink {link}: {e}")

        for folder in remove_dirs:
            try:
                shutil.rmtree(folder)
                logger.debug(f"Removed folder: {folder}")
            except Exception as e:
                logger.warning(f"Failed to remove folder {folder}: {e}")

        if ignore_files:
            logger.warning(f"Ignoring files: {[f.name for f in ignore_files]}")

    # ---------------------------------------------------------------------- #
    def _create_required_dirs(self):
        """Ensure all required Arma directories exist."""
        required = [
            self.cfg.keys_dir,
            self.cfg.mods_dir,
            self.cfg.servermods_dir,
            self.cfg.tmp_dir,
        ]

        for folder in required:
            folder = Path(folder)
            folder.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory: {folder}")

    # ---------------------------------------------------------------------- #
    def _link_shared_resources(self):
        """Symlink shared configuration, DLCs, logs, and missions."""
        logger.debug("Linking shared config directories and DLCs...")

        links = [
            (self.this_share / "config", self.arma_root / "config"),
            (self.this_share / "userconfig", self.arma_root / "userconfig"),
            (self.this_share / "logs", self.arma_root / "logs"),
            (self.common_share / "basic.cfg", self.arma_root / "basic.cfg"),
        ]

        # DLCs
        dlc_path = self.common_share / "dlcs"
        if dlc_path.exists():
            for dlc in dlc_path.iterdir():
                links.append((dlc, self.arma_root / dlc.name))

        # mpmissions (optional)
        missions = self.this_share / "mpmissions"
        if missions.exists():
            links.append((missions, self.arma_root / "mpmissions"))

        for src, dst in links:
            self._safe_link(src, dst)

    # ---------------------------------------------------------------------- #
    def _safe_link(self, src: Path, dst: Path):
        """Create a symlink with proper logging and error handling."""
        try:
            if dst.exists() or dst.is_symlink():
                logger.debug(f"Skipping existing link: {dst}")
                return
            os.symlink(src, dst)
            logger.info(f"Linked {dst} → {src}")
        except Exception as e:
            logger.error(f"Failed to link {dst} → {src}: {e}")

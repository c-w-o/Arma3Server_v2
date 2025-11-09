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
        
        #self.arma_root = config.arma_root
        #self.common_share = Path("/var/run/share/arma3/server-common")
        #self.this_share = Path("/var/run/share/arma3/this-server")
        
        #self.this_server_mods = self.this_share / "mods"
        #self.this_mission_mods = self.this_share / "mods"
        #self.common_server_mods = self.common_share / "mods"
        #self.common_base_mods = self.common_share / "mods"
        #self.common_maps = self.common_share / "mods"
        

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

        logger.debug(f"Cleaning up {self.cfg.arma_root} ...")

        for item in self.cfg.arma_root.iterdir():
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
            (self.cfg.this_share / "config", self.cfg.arma_root / "config"),
            (self.cfg.this_share / "userconfig", self.cfg.arma_root / "userconfig"),
            (self.cfg.this_share / "logs", self.cfg.arma_root / "logs"),
            (self.cfg.common_share / "basic.cfg", self.cfg.arma_root / "basic.cfg"),
        ]

        # DLCs
        dlc_path = self.cfg.common_share / "dlcs"
        all_exts = {**self.cfg.dlc_key_map, **self.cfg.bonus_key_map}
        if not dlc_path.exists():
            logger.error("no \"dlcs\" in server common found")
            exit(0)
            
        for name,short in all_exts.items():
            src_candidate = dlc_path / short
            if not src_candidate.exists():
                logger.debug(f"DLC/Extension {name} not present in common_share, should be downloaded: {src_candidate}")
                os.makedirs(src_candidate)
            links.append((src_candidate, self.cfg.arma_root / short))


        # mpmissions (optional)
        missions_candidate = self.cfg.this_share / "mpmissions"
        if not missions_candidate.exists():
            logger.error("no \"mpmissions\" in this server found")
            exit(0)
            
        links.append((missions_candidate, self.cfg.arma_root / "mpmissions"))

        for src, dst in links:
            if src is None:
                continue
            self._safe_link(src, dst)

    # ---------------------------------------------------------------------- #
    def _safe_link(self, src: Path, dst: Path):
        """Create a symlink with proper logging and error handling."""
        try:
            # If dst is a symlink, check target
            if dst.is_symlink():
                try:
                    current = os.readlink(dst)
                except Exception:
                    current = None
                if current:
                    # If the symlink already points to the desired source, skip
                    if os.path.abspath(current) == os.path.abspath(str(src)):
                        logger.debug(f"Symlink already correct: {dst} -> {current}")
                        return
                    # otherwise remove and recreate
                    try:
                        dst.unlink()
                        logger.debug(f"Removed stale symlink: {dst} (was -> {current})")
                    except Exception as e:
                        logger.warning(f"Failed to remove existing symlink {dst}: {e}")
                        return
            # If dst exists and is not a symlink, avoid overwriting
            if dst.exists() and not dst.is_symlink():
                logger.warning(f"Target exists and is not a symlink, skipping link: {dst}")
                return

            # Ensure parent exists
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(str(src), str(dst))
            logger.info(f"Linked {dst} → {src}")
        except Exception as e:
            logger.error(f"Failed to link {dst} → {src}: {e}")

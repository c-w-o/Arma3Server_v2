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

        def _resolve_case(path: Path):
            """
            If path exists return it. Otherwise try to find a case-insensitive
            match in the parent directory and return that Path. Returns None if
            not found.
            """
            if path.exists():
                return path
            parent = path.parent
            if not parent.exists():
                return None
            target_name = path.name.lower()
            for p in parent.iterdir():
                if p.name.lower() == target_name:
                    return p
            return None

        # DLCs
        dlc_path = self.cfg.common_share / "dlcs"
        dlc_shortnames = ["contact", "csla", "gm", "vn", "ws", "spe", "rf", "ef"]
        linked_dlcs = []
        if dlc_path.exists():
            for short in dlc_shortnames:
                src_candidate = dlc_path / short
                actual_src = _resolve_case(src_candidate)
                if actual_src:
                    # keep actual case from the filesystem when creating link target name
                    links.append((actual_src, self.cfg.arma_root / actual_src.name))
                    linked_dlcs.append(actual_src.name)
                else:
                    logger.debug(f"DLC not present in common_share, skipping: {src_candidate}")

        # mpmissions (optional)
        missions_candidate = self.cfg.this_share / "mpmissions"
        actual_missions = _resolve_case(missions_candidate)
        if actual_missions:
            links.append((actual_missions, self.cfg.arma_root / "mpmissions"))

        for src, dst in links:
            if src is None:
                continue
            self._safe_link(src, dst)

        # Copy keys into the keys_dir (merge from this_share and common_share).
        # Overwrite existing files to ensure current keys are present.
        def _copy_keys(src_root: Path, dst_root: Path):
            if not src_root or not src_root.exists():
                return
            for item in src_root.iterdir():
                target = dst_root / item.name
                try:
                    if item.is_dir():
                        if target.exists():
                            # merge directory contents
                            for child in item.iterdir():
                                child_tgt = target / child.name
                                if child.is_dir():
                                    if not child_tgt.exists():
                                        shutil.copytree(child, child_tgt)
                                else:
                                    shutil.copy2(child, child_tgt)
                        else:
                            shutil.copytree(item, target)
                    else:
                        # file
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, target)
                    logger.debug(f"Copied key resource {item} -> {target}")
                except Exception as e:
                    logger.warning(f"Failed to copy key {item} -> {target}: {e}")

        # Ensure keys_dir exists and copy keys (this_share preferred, then common_share)
        Path(self.cfg.keys_dir).mkdir(parents=True, exist_ok=True)
        _copy_keys(self.cfg.this_share / "keys", Path(self.cfg.keys_dir))
        _copy_keys(self.cfg.common_share / "keys", Path(self.cfg.keys_dir))

        # If we linked DLCs, ensure they are present in the -mod parameter (at the beginning).
        # Merge with any existing -mod parameter instead of duplicating.
        if linked_dlcs:
            try:
                # prefer existing params on config object, otherwise use merged params
                params = getattr(self.cfg, "params", None)
                if params is None:
                    merged = self.cfg.get_merged_config()
                    params = list(merged.get("params", []) or [])
                    setattr(self.cfg, "params", params)

                # find existing -mod entry if any
                mod_index = None
                existing_mods = []
                for idx, p in enumerate(list(params)):
                    if isinstance(p, str) and p.startswith("-mod="):
                        mod_index = idx
                        val = p.split("=", 1)[1]
                        existing_mods = [m.lstrip("@") for m in val.split(";") if m]
                        break

                # merge keeping order: linked_dlcs first, then existing unique mods
                merged_list = []
                for d in linked_dlcs:
                    if d not in merged_list:
                        merged_list.append(d)
                for m in existing_mods:
                    if m not in merged_list:
                        merged_list.append(m)

                mod_param = "-mod=" + ";".join(f"@{m}" for m in merged_list)

                if mod_index is not None:
                    params[mod_index] = mod_param
                else:
                    params.insert(0, mod_param)

                logger.info(f"Updated params with DLCs in -mod: {mod_param}")
            except Exception as e:
                logger.warning(f"Failed to update -mod parameter with DLCs: {e}")

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

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

        # Resolve effective mod lists by merging defaults + active config and removing minus-mods
        effective = self._get_effective_mod_lists()
        
        mods_to_download = []
        # consider all mod categories for download
        for key, modlist in effective.items():
            for entry in modlist:
                # expect entries as [name, steamid]
                try:
                    name, steamid = entry[0], entry[1]
                except Exception:
                    logger.debug("Skipping invalid mod entry (not a pair): %s", entry)
                    continue
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
            logger.debug(f"steam download {steamid} ({name})")
            #self.steam.download_mod(steamid)

        # Link all mods into Arma directories
        self._link_all_mods()
        logger.info("Mod synchronization complete.")
        return True

    # ---------------------------------------------------------------------- #
    def _link_all_mods(self):
        """Create symbolic links for mods and servermods from workshop."""
        logger.debug("Linking all mods into %s and %s...", self.mods_dir, self.servermods_dir)

        effective = self._get_effective_mod_lists()
        all_mods = []

        # serverMods go to servermods_dir, everything else to mods_dir
        for name, steamid in effective.get("serverMods", []):
            if not steamid:
                continue
            src = self.workshop_dir / steamid
            dst = self.servermods_dir / f"@{name}"
            self._safe_link(src, dst)
            self._copy_keys(src, name, steamid)
            all_mods.append(dst)

        for cat in ("baseMods", "clientMods", "missionMods", "maps"):
            for name, steamid in effective.get(cat, []):
                if not steamid:
                    continue
                src = self.workshop_dir / steamid
                dst = self.mods_dir / f"@{name}"
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

    # ---------------------------------------------------------------------- #
    def _get_effective_mod_lists(self):
        """
        Build effective mod lists by merging defaults.mods with active config.mods,
        then removing any entries mentioned in minus-mods.
        Returns a dict with keys like serverMods, baseMods, clientMods, missionMods, maps.
        """
        
        # try to obtain raw config structure (supporting either object or dict)
        json_data = getattr(self.cfg, "json_data", None)
        if json_data is None:
            logger.error("no \"json_data\" found or loaded in internal structure")
            return {}
        
        defaults = json_data.get("defaults", {})
        configs = json_data.get("configs", {})
        active_name=json_data.get("config-name", None)
        if active_name is None:
            logger.error("no active setup selected")
            return {}
        active = configs.get(active_name, {})
        # try common places for active config
        
        defaults_mods = defaults.get("mods", {})
        active_mods = active.get("mods", {})
        logger.debug(f"defaults_mods: {defaults_mods}")
        logger.debug(f"active_mods: {active_mods}")
        logger.debug(f"defaults: {defaults}")
        logger.debug(f"active: {active}")
        # start with defaults, then extend with active
        keys = set(list(defaults_mods.keys()) + list(active_mods.keys()))
        effective = {}
        for k in keys:
            dlist = defaults_mods.get(k, []) if isinstance(defaults_mods, dict) else []
            alist = active_mods.get(k, []) if isinstance(active_mods, dict) else []
            # ensure lists and shallow copy
            effective[k] = list(dlist) + list(alist)

        # collect minus-mods (from active only)
        minus = active_mods.get("minus-mods", []) if isinstance(active_mods, dict) else []
        if minus:
            def _normalize(entry):
                if isinstance(entry, (list, tuple)) and entry:
                    return str(entry[0]), (str(entry[1]) if len(entry) > 1 else None)
                if isinstance(entry, dict):
                    return (entry.get("name"), entry.get("steamid"))
                return (str(entry), None)

            to_remove = [_normalize(m) for m in minus]

            for k, lst in effective.items():
                new_lst = []
                for entry in lst:
                    try:
                        ename, esid = str(entry[0]), str(entry[1]) if entry[1] is not None else None
                    except Exception:
                        # keep invalid entries unchanged
                        new_lst.append(entry)
                        continue
                    skip = False
                    for rname, rsid in to_remove:
                        if rname and ename == rname:
                            skip = True
                            break
                        if rsid and esid == rsid:
                            skip = True
                            break
                    if not skip:
                        new_lst.append(entry)
                effective[k] = new_lst

        # ensure common keys exist
        for req in ("serverMods", "baseMods", "clientMods", "missionMods", "maps"):
            effective.setdefault(req, [])

        # --- NEW: combine baseMods + missionMods into missionMods and deduplicate ---
        combined_src = effective.get("baseMods", []) + effective.get("missionMods", [])
        combined = []
        seen = set()
        for entry in combined_src:
            try:
                ename = str(entry[0])
                esid = str(entry[1]) if entry[1] is not None else None
            except Exception:
                # fallback for non-pair entries
                ename = str(entry)
                esid = None
            key = (ename, esid)
            if key in seen:
                continue
            seen.add(key)
            combined.append(entry)
        effective["missionMods"] = combined        
        effective.pop("baseMods", None)

        return effective

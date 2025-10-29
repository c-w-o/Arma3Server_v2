"""
mods.py — Mod management and linking system for Arma 3 server
--------------------------------------------------------------
Handles mod linking, SteamCMD updates, key copying, and workshop synchronization.
"""

import os
import glob
import shutil
import json
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
        # extensions to force to lower-case (can be overridden in config as 'normalize_exts')
        self.normalize_exts = getattr(config, "normalize_exts", [".pbo", ".paa", ".sqf"])
        
        self._server_mod_names=[]
        self._mod_names=[]
    
    def get_server_mod_names():
        return self._server_mod_names
    
    def get_mod_names():
        return self._mod_names
    
    
    def resolve_path(self, key):
        path=None
        if key == "maps":
            path=self.cfg.common_maps
        if key == "serverMods":
            path=self.cfg.common_server_mods
        if key == "clientMods":
            path=self.cfg.common_base_mods
        if key == "missionMods":
            path=self.cfg.common_base_mods
        if key == "baseMods":
            path=self.cfg.common_base_mods
        if key == "extraServer":
            path=self.cfg.this_server_mods
        if key == "extraMission":
            path=self.cfg.this_mission_mods
        
        if path is None:
            logger.warning(f"unknown mod key: {key}")

        return path
    
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
        from datetime import datetime
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
                #mod_path = self.workshop_dir / steamid
                mod_path = self.resolve_path(key)
                if mod_path is None:
                    continue
                mod_path = mod_path / steamid
                # If missing -> download. If present, compare workshop last update date with local mtime.
                need_download = False
                remote_dt = self.steam.get_last_update_date(steamid)
                if not mod_path.exists():
                    need_download = True
                    logger.info(f"Missing mod {key} - {name} ({steamid}) — queued for download.")
                else:
                    try:
                        # compare remote update time vs local mtime (both UTC)
                        if remote_dt is None:
                            logger.warning(f"Mod {name} ({steamid}) couldn't get update information, won't update now")
                        else:
                            local_dt = self.steam.get_local_update_time(mod_path)
                            if remote_dt > local_dt:
                                need_download = True
                                logger.info(f"Mod {key} - {name} ({steamid}) outdated: remote {remote_dt} > local {local_dt}")
                            else:
                                logger.debug(f"Mod {key} - {name} ({steamid}) is up-to-date.")
                            
                    except Exception as e:
                        logger.debug(f"Error checking update date for {steamid}: {e}")
                if need_download:
                    mods_to_download.append((name, steamid, mod_path, remote_dt))

        # Download missing mods
        from time import time
        for name, steamid, mod_path, remote_dt in mods_to_download:
               
            ok = self.steam.download_mod(steamid, name, mod_path)
            if ok:
                # Normalize case of folders and selected file extensions to lower-case
                try:
                    self._normalize_mod_case(mod_path)
                except Exception as e:
                    logger.warning(f"Case-normalization failed for {mod_path}: {e}")
                self.steam.set_local_update_time(mod_path, steamid, name, remote_dt)
            else:
                logger.warning(f"Download failed for {steamid}, metadata not updated.")

        # Link all mods into Arma directories
        self._link_all_mods()
        logger.info("Mod synchronization complete.")
        return True

    # ---------------------------------------------------------------------- #
    def _link_all_mods(self):
        """Create symbolic links for mods and servermods from workshop."""
        logger.debug("Linking all mods into %s and %s...", self.mods_dir, self.servermods_dir)
        self._server_mod_names=[]
        self._mod_names=[]
        effective = self._get_effective_mod_lists()
        all_mods = []
        for key, modlist in effective.items():
            for name, steamid in modlist:
                mod_path = self.resolve_path(key)
                if mod_path is None:
                    continue
                mod_path = mod_path / steamid
                if key=="serverMods" or key=="extraServer":
                    dst = self.servermods_dir / f"@{name}"
                    self._server_mod_names.append(f"@{name}")
                else:
                    dst = self.mods_dir / f"@{name}"
                    if key!="clientMods":
                        self._mod_names.append(f"@{name}")
                self._normalize_mod_case(mod_path)
                if key!="clientMods":
                    self._safe_link(mod_path, dst)
                self._copy_keys(mod_path, name, steamid)
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
    def _safe_rename(self, old: Path, new: Path) -> bool:
        """Rename path handling case-only renames on Windows and avoiding collisions."""
        if old == new:
            return True
        try:
            if new.exists():
                # if target exists and is not the same, skip to avoid collision
                if old.resolve() != new.resolve():
                    logger.error(f"Cannot rename {old} → {new}: target exists")
                    return False
                else:
                    return True
        except Exception:
            # ignore resolve errors and attempt rename
            pass

        try:
            # Windows: case-only rename needs an intermediate name
            if os.name == "nt" and old.name.lower() == new.name.lower() and old.name != new.name:
                tmp = old.with_name(old.name + ".casechg_tmp")
                os.replace(old, tmp)
                os.replace(tmp, new)
            else:
                os.replace(old, new)
            logger.debug(f"Renamed {old} → {new}")
            return True
        except Exception as e:
            logger.error(f"Failed to rename {old} → {new}: {e}")
            return False

    # ---------------------------------------------------------------------- #
    def _normalize_mod_case(self, mod_path: Path):
        """
        Recursively lowercase directory names and file names for configured extensions.
        Handles collisions and case-only renames on Windows.
        """
        if not mod_path.exists():
            logger.warning(f"Normalize: path does not exist: {mod_path}")
            return

        # Walk bottom-up to rename files then directories
        for root, dirs, files in os.walk(mod_path, topdown=False):
            root_path = Path(root)
            # files: rename selected extensions to lower-case names
            for fname in files:
                fpath = root_path / fname
                suffix = fpath.suffix.lower()
                if suffix in [e.lower() for e in self.normalize_exts]:
                    new_name = fpath.name.lower()
                    new_path = fpath.with_name(new_name)
                    if fpath != new_path:
                        # avoid collisions
                        if new_path.exists() and new_path.resolve() != fpath.resolve():
                            logger.error(f"Normalization collision: {fpath} -> {new_path} (target exists)")
                            continue
                        self._safe_rename(fpath, new_path)

            # directories: rename to lower-case
            for dname in dirs:
                dpath = root_path / dname
                new_dname = dname.lower()
                new_dpath = dpath.with_name(new_dname)
                if dpath != new_dpath:
                    if new_dpath.exists() and new_dpath.resolve() != dpath.resolve():
                        logger.error(f"Normalization collision: {dpath} -> {new_dpath} (target exists)")
                        continue
                    self._safe_rename(dpath, new_dpath)

    # ---------------------------------------------------------------------- #
    def _copy_keys(self, moddir: Path, dispname: str, steamid: str):
        """Copies all .bikey files from a mod to the server's keys folder."""
        found = []
        
        # ensure keys dir exists
        try:
            self.keys_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to ensure keys_dir {self.keys_dir}: {e}")
            return
        
        # Walk and find .bikey files case-insensitively
        for root, _, files in os.walk(moddir):
            for fn in files:
                if Path(fn).suffix.lower() == ".bikey":
                    found.append(Path(root) / fn)

        if not found:
            logger.warning(f"No keys found for mod {dispname} ({steamid})")
            return

        for key_file in found:
            try:
                target = self.keys_dir / f"{steamid}_{key_file.name}"
                shutil.copy2(str(key_file), str(target))
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
        for req in ("serverMods", "baseMods", "clientMods", "missionMods", "maps", "extraServer", "extraMission"):
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
        logger.debug(f"effective mods: {effective}")
        return effective




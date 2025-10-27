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

        # load metadata (steamid -> {last_update_remote, last_download})
        self._meta = self._load_meta()

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
                mod_path = self.workshop_dir / steamid
                # If missing -> download. If present, compare workshop last update date with local mtime.
                need_download = False
                if not mod_path.exists():
                    need_download = True
                    logger.info(f"Missing mod {name} ({steamid}) — queued for download.")
                else:
                    try:
                        # compare remote update time vs local mtime (both UTC)
                        remote_dt = self.steam.get_last_update_date(steamid)
                        if remote_dt:
                            local_dt = datetime.utcfromtimestamp(mod_path.stat().st_mtime)
                            if remote_dt > local_dt:
                                need_download = True
                                logger.info(f"Mod {name} ({steamid}) outdated: remote {remote_dt} > local {local_dt}")
                            else:
                                logger.debug(f"Mod {name} ({steamid}) is up-to-date.")
                        else:
                            # optional: fall back to metadata stored from previous downloads
                            meta = self._meta.get(str(steamid))
                            if meta and meta.get("last_update_remote"):
                                local_dt = datetime.utcfromtimestamp(mod_path.stat().st_mtime)
                                remote_epoch = meta.get("last_update_remote")
                                from datetime import datetime as _dt
                                remote_dt_meta = _dt.utcfromtimestamp(remote_epoch)
                                if remote_dt_meta > local_dt:
                                    need_download = True
                                    logger.info(f"Mod {name} ({steamid}) outdated by stored meta: remote {remote_dt_meta} > local {local_dt}")
                                else:
                                    logger.debug(f"Mod {name} ({steamid}) up-to-date according to stored meta.")
                            else:
                                logger.debug(f"No remote update date for {steamid}; skipping remote check.")
                    except Exception as e:
                        logger.debug(f"Error checking update date for {steamid}: {e}")
                if need_download:
                    mods_to_download.append((name, steamid, key))

        # Download missing mods
        from time import time
        for name, steamid, key in mods_to_download:
            path=None
            if key == "maps":
                path=self.common_maps
            if key == "serverMods":
                path=self.common_maps
            if key == "clientMods":
                path=self.common_base_mods
            if key == "missionMods":
                path=self.this_mission_mods
            if key == "baseMods":
                path=self.common_base_mods
            
            if path is None:
                logger.warning(f"unknown mod key: {key}")
                continue
                
            ok = self.steam.download_mod(steamid, name, path)
            if ok:
                # try to get remote update date; if unavailable store download time
                try:
                    remote_dt = self.steam.get_last_update_date(steamid)
                    if remote_dt:
                        remote_epoch = int(remote_dt.timestamp())
                    else:
                        remote_epoch = int(time())
                except Exception:
                    remote_epoch = int(time())
                self._meta[str(steamid)] = {
                    "last_update_remote": remote_epoch,
                    "last_download": int(time())
                }
                self._save_meta()
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
        logger.debug(f"effective mods: {effective}")
        return effective

    def _meta_path(self) -> Path:
        # kept for backward-compat / compatibility but not used for storage anymore
        return self.workshop_dir / ".mods-meta.json"
 
    def _load_meta(self) -> dict:
        """
        Load per-mod metadata files from each mod folder:
        workshop_dir/<steamid>/.modmeta.json
        """
        import json
        meta = {}
        try:
            if not self.workshop_dir.exists():
                return {}
            for p in self.workshop_dir.glob("*/.modmeta.json"):
                try:
                    sid = p.parent.name
                    with p.open("r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    meta[str(sid)] = data
                except Exception as e:
                    logger.debug(f"Failed to load per-mod meta {p}: {e}")
        except Exception as e:
            logger.debug(f"Failed to scan workshop dir for mod meta: {e}")
        return meta
 
    def _save_meta(self):
        """
        Persist metadata by writing a .modmeta.json into each mod folder.
        Entries in self._meta are expected keyed by steamid (string).
        """
        import json
        try:
            for sid, data in list(self._meta.items()):
                try:
                    mod_dir = self.workshop_dir / str(sid)
                    mod_dir.mkdir(parents=True, exist_ok=True)
                    p = mod_dir / ".modmeta.json"
                    tmp = p.with_suffix(".tmp")
                    with tmp.open("w", encoding="utf-8") as fh:
                        json.dump(data, fh, indent=2, ensure_ascii=False)
                    tmp.replace(p)
                except Exception as e:
                    logger.error(f"Failed to write per-mod meta for {sid}: {e}")
        except Exception as e:
            logger.error(f"Failed to save mod meta: {e}")

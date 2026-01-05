from __future__ import annotations
import json
import os
import shutil
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from .models import MergedConfig, WorkshopItem, DlcSpec
from .settings import Settings
from .fs_layout import Layout
from .steamcmd import SteamCMD, SteamCmdError
from .logging_setup import get_logger
from .planner import Plan, PlanAction

log = get_logger("arma.launcher.content")

@dataclass(frozen=True)
class InstallResult:
    kind: str
    id_or_app: str
    path: Path
    changed: bool

class ContentManager:
    def __init__(self, settings: Settings, layout: Layout, steamcmd: SteamCMD):
        self.settings = settings
        self.layout = layout
        self.steamcmd = steamcmd
        self.normalize_exts = [".pbo", ".paa", ".sqf"]

    # ---------------- Planning ----------------
    def plan(self, cfg: MergedConfig) -> Plan:
        actions: List[PlanAction] = []
        notes: List[str] = []
        ok = True

        validate = bool(cfg.active.steam.force_validate)
        if validate:
            notes.append("force_validate=true: SteamCMD would run validate where applicable.")

        # DLCs
        for d in cfg.active.dlcs:
            target = self.layout.dlcs / str(d.mount_name)
            marker = target / ".modmeta.json"
            will_change = not marker.exists()
            actions.append(PlanAction(
                action="install_dlc",
                target=f"{d.name} ({d.app_id})",
                detail="SteamCMD app_update into shared dlcs store",
                paths={"dest": str(target), "marker": str(marker)},
                will_change=will_change,
                severity="info" if marker.exists() else "warn",
            ))

        # Workshop items
        def plan_item(kind: str, item: WorkshopItem):
            wid = int(item.id)
            name = item.name or str(wid)
            dest_root = {"mods": self.layout.mods, "maps": self.layout.maps, "servermods": self.layout.mods}.get(kind, self.layout.mods)
            dest = dest_root / str(wid)
            marker = dest / ".modmeta.json"
            cache = self._workshop_cache_dir(wid)
            if not cache.exists():
                sev = "warn" if item.required else "info"
                detail = "SteamCMD workshop_download_item would run; cache currently missing."
            else:
                sev = "info"
                detail = "SteamCMD workshop_download_item would run; cache exists."
            actions.append(PlanAction(
                action="download_workshop",
                target=f"{kind}:{name} ({wid})",
                detail=detail,
                paths={"cache": str(cache), "dest": str(dest), "marker": str(marker)},
                will_change=not marker.exists(),
                severity=sev,
            ))

        for it in cfg.active.workshop.mods:
            plan_item("mods", it)
        for it in cfg.active.workshop.maps:
            plan_item("maps", it)
        for it in cfg.active.workshop.servermods:
            plan_item("servermods", it)

        # Symlinks
        for it in cfg.active.workshop.mods:
            src = self.layout.mods / str(it.id)
            dst = self.layout.inst_mods / str(it.id)
            actions.append(PlanAction(
                action="link",
                target=f"mods:{it.id}",
                detail="Symlink into instance mods",
                paths={"src": str(src), "dst": str(dst)},
                will_change=True,
                severity="info" if src.exists() else "warn",
            ))
        for it in cfg.active.workshop.maps:
            src = self.layout.maps / str(it.id)
            dst = self.layout.inst_mods / str(it.id)
            actions.append(PlanAction(
                action="link",
                target=f"maps:{it.id}",
                detail="Symlink into instance mods (maps are mods in Arma terms)",
                paths={"src": str(src), "dst": str(dst)},
                will_change=True,
                severity="info" if src.exists() else "warn",
            ))
        for it in cfg.active.workshop.servermods:
            src = self.layout.mods / str(it.id)
            dst = self.layout.inst_servermods / str(it.id)
            actions.append(PlanAction(
                action="link",
                target=f"servermods:{it.id}",
                detail="Symlink into instance servermods",
                paths={"src": str(src), "dst": str(dst)},
                will_change=True,
                severity="info" if src.exists() else "warn",
            ))

        # OCAP
        oc = cfg.active.ocap
        if oc.enabled:
            src = self.layout.ocap if not oc.source_subdir else (self.layout.ocap / oc.source_subdir)
            if oc.link_to not in ("mods", "servermods"):
                ok = False
                actions.append(PlanAction(
                    action="ocap_config_error",
                    target="ocap",
                    detail="ocap.link_to must be 'mods' or 'servermods'",
                    paths={"link_to": oc.link_to},
                    will_change=False,
                    severity="error",
                ))
            else:
                dst_base = self.layout.inst_mods if oc.link_to == "mods" else self.layout.inst_servermods
                dst = dst_base / oc.link_name
                actions.append(PlanAction(
                    action="link_ocap",
                    target=f"ocap:{oc.link_to}",
                    detail="Symlink custom-built OCAP mod from shared ocap store into instance",
                    paths={"src": str(src), "dst": str(dst)},
                    will_change=True,
                    severity="info" if src.exists() else "warn",
                ))

        return Plan(ok=ok, actions=actions, notes=notes)

    # ---------------- DLCs (app_id installs) ----------------
    def ensure_dlcs(self, dlcs: List[DlcSpec], *, validate: bool, dry_run: bool = False) -> List[InstallResult]:
        results: List[InstallResult] = []
        for d in dlcs:
            target = self.layout.dlcs / str(d.app_id)
            target = self.layout.dlcs / str(d.mount_name)
            marker = target / ".modmeta.json"
            before = marker.exists()
            link_dst = self.settings.arma_root / str(d.mount_name)

            if dry_run:
                results.append(InstallResult("dlc", str(d.app_id), target, changed=not before))
                continue

            if self.settings.skip_install:
                log.info("SKIP_INSTALL: not installing DLC %s (%s)", d.name, d.app_id)
            else:
                self.steamcmd.ensure_app( d.app_id, install_dir=target, validate=validate, beta_branch=d.beta_branch, beta_password=d.beta_password )
                self._write_modmeta(marker, steamid=str(d.app_id), name=d.name, timestamp=self._now_epoch())
                self._recreate_link(link_dst, target, dry_run=False)

            results.append(InstallResult("dlc", str(d.app_id), target, changed=not before))
        return results

    # ---------------- Workshop items ----------------
    _ISO_Z = "%Y-%m-%dT%H:%M:%SZ"
    
    def _workshop_cache_dir(self, workshop_id: int) -> Path:
        return ( self.settings.steam_library_root / "steamapps" / "workshop" / "content" / str(self.settings.arma_workshop_game_id) / str(workshop_id) )

    def _sync_from_cache(self, cache: Path, dest: Path) -> bool:
        tmp = dest.parent / (dest.name + ".tmp")
        if tmp.exists():
            shutil.rmtree(tmp)
        shutil.copytree(cache, tmp, dirs_exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        tmp.rename(dest)
        return True
    
    def _copy_keys_from_mod(self, moddir: Path, *, dispname: str, steamid: str) -> None:
        """
        Old launcher behavior:
        - find *.bikey (case-insensitive)
        - copy into /arma3/keys as "<steamid>_<originalname>"
        - remove old keys for same steamid prefix first (avoid buildup/stale keys)
        """
        keys_dir = self.layout.arma_keys_dir
        try:
            keys_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            log.error("Failed to ensure keys dir %s: %s", keys_dir, e)
            return

        # cleanup old keys for this mod (prefix)
        prefix = f"{steamid}_"
        try:
            for f in keys_dir.glob(f"{prefix}*.bikey"):
                f.unlink(missing_ok=True)
        except Exception:
            pass

        found: list[Path] = []
        for root, _, files in os.walk(moddir):
            for fn in files:
                if Path(fn).suffix.lower() == ".bikey":
                    found.append(Path(root) / fn)

        if not found:
            log.warning("No keys found for mod %s (%s)", dispname, steamid)
            return

        for key_file in found:
            try:
                target = keys_dir / f"{steamid}_{key_file.name}"
                shutil.copy2(str(key_file), str(target))
            except Exception as e:
                log.error("Failed to copy key %s: %s", key_file, e)
    
    def _safe_rename(self, src: Path, dst: Path) -> None:
        try:
            src.rename(dst)
        except Exception as e:
            log.error("Failed to rename %s -> %s: %s", src, dst, e)

    def _normalize_mod_case(self, mod_path: Path) -> None:
        """
        Old launcher behavior:
          - walk bottom-up
          - directories -> lower-case
          - files with selected extensions -> lower-case file name
          - avoid collisions
        """
        lower_exts = {e.lower() for e in self.normalize_exts}

        for root, dirs, files in os.walk(mod_path, topdown=False):
            root_path = Path(root)

            # files
            for fname in files:
                fpath = root_path / fname
                suffix = fpath.suffix.lower()
                if suffix in lower_exts:
                    new_path = fpath.with_name(fpath.name.lower())
                    if fpath != new_path:
                        if new_path.exists() and new_path.resolve() != fpath.resolve():
                            log.error("Normalization collision: %s -> %s (target exists)", fpath, new_path)
                            continue
                        self._safe_rename(fpath, new_path)

            # directories
            for dname in dirs:
                dpath = root_path / dname
                new_dpath = dpath.with_name(dname.lower())
                if dpath != new_dpath:
                    if new_dpath.exists() and new_dpath.resolve() != dpath.resolve():
                        log.error("Normalization collision: %s -> %s (target exists)", dpath, new_dpath)
                        continue
                    self._safe_rename(dpath, new_dpath)

    @staticmethod
    def _now_iso_z() -> str:
        return datetime.now(timezone.utc).strftime(ContentManager._ISO_Z)

    @staticmethod
    def _now_epoch() -> int:
        return int(datetime.now(timezone.utc).timestamp())

    def _read_modmeta(self, path: Path) -> Optional[dict]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_modmeta(
        self,
        path: Path,
        *,
        steamid: str,
        name: str,
        timestamp: int,
        synced_at: Optional[str] = None,
        last_checked: Optional[str] = None,
    ) -> None:
        data = {
            "steamid": str(steamid),
            "name": str(name),
            "timestamp": int(timestamp),
            "synced_at": synced_at or self._now_iso_z(),
            "last_checked": last_checked or self._now_iso_z(),
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _get_remote_time_updated_epoch(self, workshop_id: int) -> Optional[int]:
        """Steam Web API: GetPublishedFileDetails -> time_updated (epoch seconds, UTC)."""
        url = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
        post_data = urllib.parse.urlencode(
            {
                "itemcount": "1",
                "publishedfileids[0]": str(workshop_id),
            }
        ).encode("utf-8")

        req = urllib.request.Request(url, data=post_data, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
            j = json.loads(body)
            details = j.get("response", {}).get("publishedfiledetails", [])
            if not details:
                return None
            time_updated = details[0].get("time_updated")
            if not time_updated:
                return None
            return int(time_updated)
        except Exception as e:
            log.debug("GetPublishedFileDetails failed for %s: %s", workshop_id, e)
            return None

    def _is_workshop_item_up_to_date(self, wid: int, dest: Path, marker: Path, name: str) -> tuple[bool, Optional[int]]:
        """Return (up_to_date, remote_ts). Updates marker.last_checked when possible."""
        if not dest.exists() or not marker.exists():
            return (False, None)

        meta = self._read_modmeta(marker) or {}
        local_ts = int(meta.get("timestamp") or 0)

        checked = self._now_iso_z()
        remote_ts = self._get_remote_time_updated_epoch(wid)

        # Always update last_checked if we can read the marker.
        try:
            if meta:
                meta["steamid"] = str(wid)
                meta["name"] = name
                meta["timestamp"] = local_ts
                meta["synced_at"] = str(meta.get("synced_at") or checked)
                meta["last_checked"] = checked
                marker.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception:
            pass

        # If remote can't be determined, treat as not up-to-date (old launcher behavior).
        if remote_ts is None:
            return (False, None)
        
        if not self._verify_mod_minimum(dest, name):
            return (False, None)

        return (local_ts >= int(remote_ts), int(remote_ts))


    def ensure_workshop_item(self, kind: str, item: WorkshopItem, *, validate: bool, dry_run: bool = False) -> Optional[InstallResult]:
        wid = int(item.id)
        name = item.name or str(wid)

        dest_root = {"mods": self.layout.mods, "maps": self.layout.maps, "servermods": self.layout.mods}.get(kind, self.layout.mods)
        dest = dest_root / str(wid)
        marker = dest / ".modmeta.json"
        before = marker.exists()

        if dry_run:
            return InstallResult(kind, str(wid), dest, changed=not before)

        if self.settings.skip_install:
            log.info("SKIP_INSTALL: not downloading workshop %s (%s) kind=%s", name, wid, kind)
            return InstallResult(kind, str(wid), dest, changed=not before)
        
        up_to_date, remote_ts = self._is_workshop_item_up_to_date(wid, dest, marker, name)
        
        if up_to_date:
            log.info("Workshop mod up-to-date: %s (%s) kind=%s", name, wid, kind)
            return InstallResult(kind, str(wid), dest, changed=False)

        log.warning("Workshop mod not up-to-date: %s (%s) kind=%s - start downloading", name, wid, kind)
        try:
            self.steamcmd.workshop_download(self.settings.arma_workshop_game_id, wid, validate=validate)
        except SteamCmdError as e:
            # If the workshop item no longer exists / is private / access denied:
            # - required -> hard fail with a helpful message
            # - optional -> warn + skip
            if e.kind in ("NOT_FOUND", "ACCESS_DENIED"):
                msg = f"Workshop item unavailable: {name} ({wid}) kind={kind} reason={e.kind}"
                if item.required:
                    raise RuntimeError(msg) from e
                log.warning("%s - skipping optional item", msg)
                return None
            raise

        cache = self._workshop_cache_dir(wid)
        if not cache.exists():
            msg = ( f"Workshop download produced no cache directory: {cache} (item={name} id={wid} kind={kind}). Item may be removed/private, or download failed silently.")
            if item.required:
                raise RuntimeError(msg)
            log.warning("%s - skipping optional item", msg)
            return None

        changed = self._sync_from_cache(cache, dest)
        self._normalize_mod_case(dest)
        if remote_ts is None:
            remote_ts = self._get_remote_time_updated_epoch(wid) or self._now_epoch()
        self._write_modmeta(marker, steamid=str(wid), name=name, timestamp=int(remote_ts))
        self._copy_keys_from_mod(dest, dispname=name, steamid=str(wid))
        return InstallResult(kind, str(wid), dest, changed=(changed or not before))

    def _verify_mod_minimum(self, src_path: Path, name: str, required: Optional[list[str]] = None) -> bool:
        """
        Old launcher behavior:
          default required: ["addons", "meta.cpp", ".pbo"]
          - "addons" satisfied if addons/ exists OR any *.pbo exists
          - "meta.cpp" satisfied case-insensitive anywhere under mod
        """
        if required is None:
            required = ["addons", "meta.cpp", ".pbo"]

        src = Path(src_path)
        if not src.exists():
            return False

        missing: list[str] = []

        if "addons" in required:
            if (src / "addons").exists():
                pass
            elif any(src.glob("**/*.pbo")):
                pass
            else:
                missing.append("addons or .pbo")

        if "meta.cpp" in required:
            if not (src / "meta.cpp").exists():
                found_meta = any(p.name.lower() == "meta.cpp" for p in src.rglob("*") if p.is_file())
                if not found_meta:
                    missing.append("meta.cpp")

        # optional additional requirements
        for req in required:
            if req in ("addons", "meta.cpp", ".pbo"):
                continue
            if req.endswith("/"):
                if not (src / req.rstrip("/")).exists():
                    missing.append(req)
            else:
                if not (src / req).exists():
                    missing.append(req)

        if missing:
            log.debug("Validation failed for %s (%s). Missing: %s", name, src_path, missing)
            return False
        return True

    def ensure_workshop(self, cfg: MergedConfig, *, dry_run: bool = False) -> List[InstallResult]:
        validate = bool(cfg.active.steam.force_validate)
        results: List[InstallResult] = []
        failures: list[tuple[str, str, int, str]] = []  # (kind, name, wid, reason)
        
        for item in cfg.active.workshop.mods:
            try:
                r = self.ensure_workshop_item("mods", item, validate=validate, dry_run=dry_run)
                if r:
                    results.append(r)
            except Exception as e:
                wid = int(item.id)
                name = item.name or str(wid)
                reason = str(e)
                if item.required:
                    log.error("Workshop REQUIRED item failed: %s (%s) kind=mods :: %s", name, wid, reason)
                    failures.append(("mods", name, wid, reason))
                else:
                    log.warning("Workshop OPTIONAL item failed: %s (%s) kind=mods :: %s", name, wid, reason)
                continue
        for item in cfg.active.workshop.maps:
            log.info("Workshop: %s '%s' (id=%s) -> category=%s validate=%s dry_run=%s", "ensure", item.name or "<unnamed>", item.id, "maps", validate, dry_run )
            try:
                r = self.ensure_workshop_item("maps", item, validate=validate, dry_run=dry_run)
                if r:
                    results.append(r)
            except Exception as e:
                wid = int(item.id)
                name = item.name or str(wid)
                reason = str(e)
                if item.required:
                    log.error("Workshop REQUIRED item failed: %s (%s) kind=maps :: %s", name, wid, reason)
                    failures.append(("maps", name, wid, reason))
                else:
                    log.warning("Workshop OPTIONAL item failed: %s (%s) kind=maps :: %s", name, wid, reason)
                continue
        for item in cfg.active.workshop.servermods:
            log.info("Workshop: %s '%s' (id=%s) -> category=%s validate=%s dry_run=%s", "ensure", item.name or "<unnamed>", item.id, "servermods", validate, dry_run )
            try:
                r = self.ensure_workshop_item("servermods", item, validate=validate, dry_run=dry_run)
                if r:
                    results.append(r)
            except Exception as e:
                wid = int(item.id)
                name = item.name or str(wid)
                reason = str(e)
                if item.required:
                    log.error("Workshop REQUIRED item failed: %s (%s) kind=servermods :: %s", name, wid, reason)
                    failures.append(("servermods", name, wid, reason))
                else:
                    log.warning("Workshop OPTIONAL item failed: %s (%s) kind=servermods :: %s", name, wid, reason)
                continue

        if failures:
            # One final error that the caller can render in UI (without losing earlier log lines).
            msg = "Required workshop items failed:\n" + "\n".join(
                [f"- {k}: {n} ({wid}) :: {r}" for (k, n, wid, r) in failures]
            )
            raise RuntimeError(msg)
        return results

    # ---------------- Instance symlinks ----------------
    def _recreate_link(self, link_path: Path, target: Path, *, dry_run: bool = False) -> None:
        if dry_run:
            return
        if link_path.is_symlink() or link_path.exists():
            if link_path.is_dir() and not link_path.is_symlink():
                shutil.rmtree(link_path)
            else:
                link_path.unlink(missing_ok=True)
        link_path.symlink_to(target, target_is_directory=True)

    def link_instance_content(self, cfg: MergedConfig, *, dry_run: bool = False) -> None:
        if not dry_run:
            for d in [self.layout.inst_mods, self.layout.inst_servermods]:
                d.mkdir(parents=True, exist_ok=True)
                for child in list(d.iterdir()):
                    if child.is_symlink() or child.is_file():
                        child.unlink(missing_ok=True)
                    elif child.is_dir():
                        shutil.rmtree(child)

        for it in cfg.active.workshop.mods:
            src = self.layout.mods / str(it.id)
            if src.exists():
                self._recreate_link(self.layout.inst_mods / str(it.id), src, dry_run=dry_run)

        for it in cfg.active.workshop.maps:
            src = self.layout.maps / str(it.id)
            if src.exists():
                self._recreate_link(self.layout.inst_mods / str(it.id), src, dry_run=dry_run)

        for it in cfg.active.workshop.servermods:
            src = self.layout.mods / str(it.id)
            if src.exists():
                self._recreate_link(self.layout.inst_servermods / str(it.id), src, dry_run=dry_run)

        # OCAP custom build
        oc = cfg.active.ocap
        if oc.enabled:
            src = self.layout.ocap if not oc.source_subdir else (self.layout.ocap / oc.source_subdir)
            dst_base = self.layout.inst_mods if oc.link_to == "mods" else self.layout.inst_servermods
            self._recreate_link(dst_base / oc.link_name, src, dry_run=dry_run)

        log.info("Instance symlinks prepared%s.", " (dry-run)" if dry_run else "")

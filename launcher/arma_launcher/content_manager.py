from __future__ import annotations
import json
import itertools
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
            dest_root = {"mods": self.layout.mods, "clientmods": self.layout.mods, "maps": self.layout.maps, "servermods": self.layout.servermods}.get(kind, self.layout.mods)
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
                
        # Custom (non-Steam) mods: folder names under instance custom-mods mount
        cm = cfg.active.custom_mods
        for name in (cm.mods or []):
            src = self._resolve_custom_mod_dir(name)
            token = str(name).strip()
            if token.startswith("@"):
                token = token[1:]
            actions.append(PlanAction(
                action="link_custom_mod",
                target=f"custom-mod:{token}",
                detail="Symlink custom mod folder into game root and instance mods",
                paths={"src": str(src), "dst_root": str(self.settings.arma_root / ("@"+token)), "dst_inst": str(self.layout.inst_mods / token)},
                will_change=True,
                severity="info" if src.exists() else "warn",
            ))
        for name in (cm.servermods or []):
            src = self._resolve_custom_mod_dir(name)
            token = str(name).strip()
            if token.startswith("@"):
                token = token[1:]
            actions.append(PlanAction(
                action="link_custom_servermod",
                target=f"custom-servermod:{token}",
                detail="Symlink custom servermod folder into game root and instance servermods",
                paths={"src": str(src), "dst_root": str(self.settings.arma_root / ("@"+token)), "dst_inst": str(self.layout.inst_servermods / token)},
                will_change=True,
                severity="info" if src.exists() else "warn",
            ))

        return Plan(ok=ok, actions=actions, notes=notes)

    def _resolve_dlc_link_source(self, target: Path, mount_name: str) -> Path:
        """
        SteamCMD installs for Creator DLCs sometimes result in layouts like:
          <target>/addons
          <target>/<mount_name>/addons
          <target>/<something>/addons

        The server expects /arma3/<mount_name> to be the folder that contains 'addons/'.
        We therefore pick the most plausible folder to link.
        """
        # 1) direct
        if (target / "addons").exists():
            return target

        # 2) nested by mount_name
        candidate = target / mount_name
        if (candidate / "addons").exists():
            return candidate

        # 3) any immediate child with addons
        try:
            children = [p for p in target.iterdir() if p.is_dir()]
        except Exception:
            children = []

        hits = [p for p in children if (p / "addons").exists()]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            # deterministic pick, but warn
            pick = sorted(hits, key=lambda x: x.name)[0]
            log.warning("DLC layout ambiguous under %s (multiple addons/ dirs). Picking %s", target, pick)
            return pick

        # 4) fallback: link the target; server may still work if structure is flat but different
        log.warning("Could not find 'addons' folder in DLC install at %s; linking install root", target)
        return target

    def ensure_bonus_folders_linked(self, names: list[str], *, dry_run: bool = False) -> None:
        """
        Old-launcher parity:
        Ensure selected built-in/bonus folders (e.g. aow/argo/curator) live in shared dlcs store
        and are symlinked into the game root (/arma3/<name>).
        If the folder currently exists as a real dir in /arma3, migrate it into the shared store first.
        """
        for name in names:
            token = str(name).strip().lower()
            if not token:
                continue

            store = self.layout.dlcs / token
            link_dst = self.settings.arma_root / token

            if dry_run:
                continue

            # Ensure shared store exists
            store.parent.mkdir(parents=True, exist_ok=True)

            # MIGRATION: if /arma3/<token> exists as a real dir, move it into the shared store
            if link_dst.exists() and link_dst.is_dir() and not link_dst.is_symlink():
                # If store already exists and has content, we do NOT overwrite it.
                if store.exists() and any(store.iterdir()):
                    log.warning("Bonus folder %s exists in game root and store already non-empty; leaving game root as-is: %s", token, link_dst)
                else:
                    # replace empty/non-existing store with migrated content
                    if store.exists():
                        shutil.rmtree(store)
                    try:
                        shutil.move(str(link_dst), str(store))
                        log.info("Migrated bonus folder %s from %s -> %s", token, link_dst, store)
                    except Exception as e:
                        log.error("Failed to migrate bonus folder %s: %s", token, e)
                        continue

            # If store doesn't exist yet, create it (empty is okay)
            store.mkdir(parents=True, exist_ok=True)

            # Finally ensure /arma3/<token> is a symlink to shared store
            self._recreate_link(link_dst, store, dry_run=False)
            log.info("Linked bonus folder %s: %s -> %s", token, link_dst, store)
    
    # ---------------- DLCs (app_id installs) ----------------
    def ensure_dlcs(self, dlcs: List[DlcSpec], *, validate: bool, dry_run: bool = False) -> List[InstallResult]:
        results: List[InstallResult] = []
        for d in dlcs:
            target = self.layout.dlcs / str(d.mount_name)
            marker = target / ".modmeta.json"
            before = marker.exists()

            link_dst_legacy = self.settings.arma_root / str(d.mount_name)
            link_dst_dir = self.settings.arma_root / "dlcs" / str(d.mount_name)

            if dry_run:
                results.append(InstallResult("dlc", str(d.app_id), target, changed=not before))
                continue

            if self.settings.skip_install:
                log.info("SKIP_INSTALL: not installing DLC %s (%s)", d.name, d.app_id)
            else:
                # Install into the shared DLC store (host mounted)
                self.steamcmd.ensure_app(
                    d.app_id,
                    install_dir=target,
                    validate=validate,
                    beta_branch=d.beta_branch,
                    beta_password=d.beta_password,
                )
                self._write_modmeta(marker, steamid=str(d.app_id), name=d.name, timestamp=self._now_epoch())
                link_src = self._resolve_dlc_link_source(target, str(d.mount_name))
                try:
                    (self.settings.arma_root / "dlcs").mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass

                self._recreate_link(link_dst_legacy, link_src, dry_run=False)
                self._recreate_link(link_dst_dir, link_src, dry_run=False)

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

    def _resolve_custom_mod_dir(self, name: str) -> Path:
        """Resolve a custom-mod folder name to an existing directory.
 
        Accepts either "myMod" or "@myMod" as folder names on disk.
        We normalize tokens to "@myMod" on the arma_root side.
        """
        raw = str(name).strip()
        if not raw:
            return self.layout.inst_custom_mods
        # try exact
        p1 = self.layout.inst_custom_mods / raw
        if p1.exists():
            return p1
        # if name doesn't start with '@', also try '@<name>'
        if not raw.startswith('@'):
            p2 = self.layout.inst_custom_mods / ('@' + raw)
            if p2.exists():
                return p2
        # if name starts with '@', also try without
        if raw.startswith('@'):
            p3 = self.layout.inst_custom_mods / raw.lstrip('@')
            if p3.exists():
                return p3
        return p1
 
    def _ensure_custom_mods_links(self, cfg: MergedConfig, *, dry_run: bool = False) -> None:
        """Expose instance-mounted custom mods in places the server can load them.
 
        We create:
          - /arma3/custom-mods -> <instance>/custom-mods
          - /arma3/@<name> -> <instance>/custom-mods/<name>
          - <instance>/mods/<name> -> <instance>/custom-mods/<name> (fallback)
          - <instance>/servermods/<name> -> <instance>/custom-mods/<name> (fallback)
        """
        # Link the root folder
        if self.layout.arma_custom_mods_dir.exists() and self.layout.arma_custom_mods_dir.is_dir() and not self.layout.arma_custom_mods_dir.is_symlink():
            # keep directory if already created by something else
            pass
        else:
            self._symlink(src=self.layout.inst_custom_mods, dst=self.layout.arma_custom_mods_dir, dry_run=dry_run)
 
        def link_one(name: str, kind: str) -> None:
            src_dir = self._resolve_custom_mod_dir(name)
            token = str(name).strip()
            if token.startswith('@'):
                token = token[1:]
            if not token:
                return
            dst_token = self.settings.arma_root / f"@{token}"
            self._symlink(src=src_dir, dst=dst_token, dry_run=dry_run)
            if kind == 'mods':
                self._symlink(src=src_dir, dst=self.layout.inst_mods / token, dry_run=dry_run)
            else:
                self._symlink(src=src_dir, dst=self.layout.inst_servermods / token, dry_run=dry_run)
 
        for name in cfg.active.custom_mods.mods:
            link_one(name, 'mods')
        for name in cfg.active.custom_mods.servermods:
            link_one(name, 'servermods')

    def ensure_workshop_item(self, kind: str, item: WorkshopItem, *, validate: bool, dry_run: bool = False) -> Optional[InstallResult]:
        wid = int(item.id)
        name = item.name or str(wid)

        dest_root = {"mods": self.layout.mods, "clientmods": self.layout.mods, "maps": self.layout.maps, "servermods": self.layout.servermods}.get(kind, self.layout.mods)
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
            # SteamCMD can hit rate limits (ERROR (Rate Limit Exceeded)).
            # We retry with exponential backoff + jitter to avoid hammering Steam.
            max_attempts = 8
            base_delay_s = 5.0
            max_delay_s = 600.0  # cap at 10 minutes

            attempt = 0
            while True:
                attempt += 1
                try:
                    self.steamcmd.workshop_download(self.settings.arma_workshop_game_id, wid, validate=validate)
                    break  # success
                except SteamCmdError as e:
                    if e.kind not in ("RATE_LIMIT", "TIMEOUT") or attempt >= max_attempts:
                        raise

                    # exponential backoff: base * 2^(attempt-1), with small jitter
                    delay = min(max_delay_s, base_delay_s * (2 ** (attempt - 1)))
                    jitter = random.uniform(0.0, min(5.0, delay * 0.1))
                    sleep_s = delay + jitter
                    log.warning(
                        "SteamCMD transient error (%s) downloading %s (%s). Retry %d/%d in %.1fs",
                        e.kind, name, wid, attempt, max_attempts, sleep_s
                    )
                    time.sleep(sleep_s)
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
        for item in cfg.active.workshop.clientmods:
            try:
                r = self.ensure_workshop_item("clientmods", item, validate=validate, dry_run=dry_run)
                if r:
                    results.append(r)
            except Exception as e:
                wid = int(item.id)
                name = item.name or str(wid)
                reason = str(e)
                if item.required:
                    log.error("Workshop REQUIRED item failed: %s (%s) kind=clientmods :: %s", name, wid, reason)
                    failures.append(("clientmods", name, wid, reason))
                else:
                    log.warning("Workshop OPTIONAL item failed: %s (%s) kind=clientmods :: %s", name, wid, reason)
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
        
        log.info(
            "Layout: inst=%s inst_mods=%s inst_mpmissions=%s inst_servermods=%s inst_config=%s",
            self.settings.arma_instance,
            self.layout.inst_mods,
            self.layout.inst_mpmissions,
            self.layout.inst_servermods,
            self.layout.inst_config,
        )
        if self.layout.inst_mods.resolve() == self.layout.inst_mpmissions.resolve():
            raise RuntimeError(
                f"Layout invalid: inst_mods and inst_mpmissions resolve to the same path: "
                f"{self.layout.inst_mods} == {self.layout.inst_mpmissions}. "
                f"This would link workshop mods into mpmissions."
            )

        if not dry_run:
            for d in [self.layout.inst_mods, self.layout.inst_servermods]:
                d.mkdir(parents=True, exist_ok=True)
                for child in list(d.iterdir()):
                    if child.is_symlink() or child.is_file():
                        child.unlink(missing_ok=True)
                    elif child.is_dir():
                        shutil.rmtree(child)
        
        def link_into_game_root(link_name: str, target: Path) -> None:
            # Create /arma3 if needed (normally exists)
            if not dry_run:
                try:
                    self.settings.arma_root.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass
            self._recreate_link(self.settings.arma_root / link_name, target, dry_run=dry_run)

        def wid_link_name(wid: str | int) -> str:
            return f"@{wid}"

        for it in cfg.active.workshop.mods:
            src = self.layout.mods / str(it.id)
            if src.exists():
                self._recreate_link(self.layout.inst_mods / str(it.id), src, dry_run=dry_run)
                link_into_game_root(wid_link_name(it.id), src)

        for it in cfg.active.workshop.maps:
            src = self.layout.maps / str(it.id)
            if src.exists():
                self._recreate_link(self.layout.inst_mods / str(it.id), src, dry_run=dry_run)
                link_into_game_root(wid_link_name(it.id), src)

        for it in cfg.active.workshop.servermods:
            src = self.layout.servermods  / str(it.id)
            if src.exists():
                self._recreate_link(self.layout.inst_servermods / str(it.id), src, dry_run=dry_run)
                link_into_game_root(wid_link_name(it.id), src)

        # OCAP custom build
        oc = cfg.active.ocap
        if oc.enabled:
            src = self.layout.ocap if not oc.source_subdir else (self.layout.ocap / oc.source_subdir)
            dst_base = self.layout.inst_mods if oc.link_to == "mods" else self.layout.inst_servermods
            self._recreate_link(dst_base / oc.link_name, src, dry_run=dry_run)
            oc_link = oc.link_name if oc.link_name.startswith("@") else f"@{oc.link_name}"
            link_into_game_root(oc_link, src)

        # --- Custom mods (non-Steam)
        cm = cfg.active.custom_mods
        for item in (cm.mods or []):
            src = self.layout.inst_custom_mods / item.name
            if src.exists():
                # fallback for absolute paths
                self._recreate_link(self.layout.inst_mods / item.name, src, dry_run=dry_run)
                link_into_game_root(self._mod_token(item.name), src)
            elif item.required:
                log.warning("Required custom mod missing: %s (expected %s)", item.name, src)

        for item in (cm.servermods or []):
            src = self.layout.inst_custom_mods / item.name
            if src.exists():
                self._recreate_link(self.layout.inst_servermods / item.name, src, dry_run=dry_run)
                link_into_game_root(self._mod_token(item.name), src)
            elif item.required:
                log.warning("Required custom servermod missing: %s (expected %s)", item.name, src)

        # --- Missions: make /arma3/mpmissions point to instance missions folder
        missions_src = self.layout.inst_mpmissions
        missions_dst = self.settings.arma_root / cfg.server.missions_dir  # usually "mpmissions"
        if not dry_run:
            missions_src.mkdir(parents=True, exist_ok=True)
        self._recreate_link(missions_dst, missions_src, dry_run=dry_run)

        # --- Config: keep instance config authoritative, but expose generated cfgs under /arma3/config as symlinks
        # Do NOT replace /arma3/config directory (game files may live there). Only link the generated files.
        inst_cfg = self.layout.inst_config
        if not dry_run:
            inst_cfg.mkdir(parents=True, exist_ok=True)
            self.layout.arma_cfg_dir.mkdir(parents=True, exist_ok=True)

        # Link generated server cfg
        self._recreate_link(
            self.layout.arma_cfg_dir / "generated_a3server.cfg",
            inst_cfg / "generated_a3server.cfg",
            dry_run=dry_run,
        )

        # Link generated HC cfg (if you generate it)
        self._recreate_link(
            self.layout.arma_cfg_dir / "generated_hc_a3client.cfg",
            inst_cfg / "generated_hc_a3client.cfg",
            dry_run=dry_run,
        )

        log.info("Instance symlinks prepared%s.", " (dry-run)" if dry_run else "")


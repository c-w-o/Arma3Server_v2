from __future__ import annotations
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from .models import MergedConfig, WorkshopItem, DlcSpec
from .settings import Settings
from .fs_layout import Layout
from .steamcmd import SteamCMD
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
            target = self.layout.dlcs / str(d.app_id)
            marker = target / ".installed"
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
            marker = dest / ".installed"
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
            target.mkdir(parents=True, exist_ok=True)
            marker = target / ".installed"
            before = marker.exists()

            if dry_run:
                results.append(InstallResult("dlc", str(d.app_id), target, changed=not before))
                continue

            if self.settings.skip_install:
                log.info("SKIP_INSTALL: not installing DLC %s (%s)", d.name, d.app_id)
            else:
                self.steamcmd.ensure_app(
                    d.app_id,
                    install_dir=target,
                    validate=validate,
                    beta_branch=d.beta_branch,
                    beta_password=d.beta_password,
                )
                marker.write_text("ok", encoding="utf-8")

            results.append(InstallResult("dlc", str(d.app_id), target, changed=not before))
        return results

    # ---------------- Workshop items ----------------
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

    def ensure_workshop_item(self, kind: str, item: WorkshopItem, *, validate: bool, dry_run: bool = False) -> Optional[InstallResult]:
        wid = int(item.id)
        name = item.name or str(wid)

        dest_root = {"mods": self.layout.mods, "maps": self.layout.maps, "servermods": self.layout.mods}.get(kind, self.layout.mods)
        dest = dest_root / str(wid)
        marker = dest / ".installed"
        before = marker.exists()

        if dry_run:
            return InstallResult(kind, str(wid), dest, changed=not before)

        if self.settings.skip_install:
            log.info("SKIP_INSTALL: not downloading workshop %s (%s) kind=%s", name, wid, kind)
            return InstallResult(kind, str(wid), dest, changed=not before)

        self.steamcmd.workshop_download(self.settings.arma_workshop_game_id, wid, validate=validate)
        cache = self._workshop_cache_dir(wid)
        if not cache.exists():
            if item.required:
                raise RuntimeError(f"Workshop download failed; cache missing: {cache}")
            log.warning("Workshop cache missing for optional item %s (%s)", name, wid)
            return None

        changed = self._sync_from_cache(cache, dest)
        marker.write_text("ok", encoding="utf-8")
        return InstallResult(kind, str(wid), dest, changed=(changed or not before))

    def ensure_workshop(self, cfg: MergedConfig, *, dry_run: bool = False) -> List[InstallResult]:
        validate = bool(cfg.active.steam.force_validate)
        results: List[InstallResult] = []
        for item in cfg.active.workshop.mods:
            r = self.ensure_workshop_item("mods", item, validate=validate, dry_run=dry_run)
            if r: results.append(r)
        for item in cfg.active.workshop.maps:
            r = self.ensure_workshop_item("maps", item, validate=validate, dry_run=dry_run)
            if r: results.append(r)
        for item in cfg.active.workshop.servermods:
            r = self.ensure_workshop_item("servermods", item, validate=validate, dry_run=dry_run)
            if r: results.append(r)
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

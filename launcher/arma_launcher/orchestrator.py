from __future__ import annotations
from pathlib import Path
from typing import List
import os
from .settings import Settings
from .logging_setup import get_logger
from .fs_layout import build_layout, ensure_dirs
from .config_loader import load_config
from .steamcmd import SteamCMD
from .content_manager import ContentManager
from .cfg_generator import generate_server_cfg, generate_profile_cfg
from .process_runner import ProcessRunner
from .planner import Plan

log = get_logger("arma.launcher.orch")

class Orchestrator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.layout = build_layout(settings)
        self.runner = ProcessRunner()
        self._cfg = None

    @property
    def cfg(self):
        if self._cfg is None:
            cfg_path = self.layout.inst_config / "server.json"
            self._cfg = load_config(cfg_path)
        return self._cfg

    def prepare_environment(self) -> None:
        ensure_dirs(self.layout)
        if not self.settings.arma_binary.exists():
            log.warning("Arma binary not found at %s (will be installed/updated via SteamCMD on run).", self.settings.arma_binary)

    def ensure_arma(self) -> None:
        if self.settings.skip_install:
            log.info("SKIP_INSTALL: not ensuring Arma dedicated server installation.")
            return
        steamcmd = SteamCMD(self.settings)

        log.info("Ensuring Arma dedicated server is installed/updated via SteamCMD (app_id=%s) into %s",
                self.settings.arma_app_id, self.settings.arma_root)

        steamcmd.ensure_app(
            app_id=self.settings.arma_app_id,
            install_dir=self.settings.arma_root,
            validate=True,
        )

    def plan(self) -> Plan:
        steamcmd = SteamCMD(self.settings)
        cm = ContentManager(self.settings, self.layout, steamcmd)
        return cm.plan(self.cfg)

    def sync_content(self, *, dry_run: bool = False) -> None:
        steamcmd = SteamCMD(self.settings)
        cm = ContentManager(self.settings, self.layout, steamcmd)
        cfg = self.cfg
        
        dlcs_n = len(cfg.active.dlcs)
        mods_n = len(cfg.active.workshop.mods)
        maps_n = len(cfg.active.workshop.maps)
        servermods_n = len(cfg.active.workshop.servermods)
        custom_mods_n = len(cfg.active.custom_mods.mods)
        custom_servermods_n = len(cfg.active.custom_mods.servermods)
        hc_n = int(cfg.active.headless_clients.count if cfg.active.headless_clients.enabled else 0)
        ocap = bool(cfg.active.ocap.enabled)

        log.info(
            "Plan: dlcs=%d mods=%d(+%d custom) maps=%d servermods=%d(+%d custom) hc=%d ocap=%s",
+            dlcs_n, mods_n, custom_mods_n, maps_n, servermods_n, custom_servermods_n, hc_n, ocap
        )
        log.info("Plan mods: %s", [f"{m.name or 'UNKNOWN'} ({m.id})" for m in cfg.active.workshop.mods])
        
        cm.ensure_dlcs(cfg.active.dlcs, validate=cfg.active.steam.force_validate, dry_run=dry_run)
        cm.ensure_workshop(cfg, dry_run=dry_run)
        cm.link_instance_content(cfg, dry_run=dry_run)

    def generate_server_cfg(self, *, dry_run: bool = False) -> Path:
        out = self.settings.arma_root / "config" / "generated_a3server.cfg"
        if dry_run:
            return out
        generate_server_cfg(self.cfg, out)
        return out

    def _server_cfg_path(self) -> Path:
        return self.layout.inst_config / "generated_a3server.cfg"

    def _hc_cfg_path(self) -> Path:
        return self.layout.inst_config / "generated_hc_a3client.cfg"


    def _build_mod_arg(self) -> str:
        parts = []
        for p in sorted(self.layout.inst_mods.iterdir()):
            if p.is_symlink() or p.is_dir():
                parts.append(str(p))
        return ";".join(parts)
    
    def _prefer_game_root_token(self, token: str) -> str:
        """
        If /arma3/<token> exists, we can pass token (e.g. "@333...") like the old launcher.
        Otherwise fall back to absolute instance path to avoid breaking startup.
        """
        p = self.settings.arma_root / token
        if p.exists():
            return token
        # fallback: translate "@123" -> "<inst_mods>/123"
        if token.startswith("@"):
            fallback = self.layout.inst_mods / token[1:]
            if fallback.exists() or fallback.is_symlink():
                return str(fallback)
        return token

    def _build_mod_arg(self, cfg) -> str:
        """
        Old-style: -mod=@id;@id;...
        Order is taken from config lists (mods first, then maps), optional OCAP if linked to mods.
        """
        parts: List[str] = []

        # regular workshop mods
        for it in cfg.active.workshop.mods:
            tok = self._mod_token(it.id)
            parts.append(self._prefer_game_root_token(tok))

        # maps are also loaded via -mod
        for it in cfg.active.workshop.maps:
            tok = self._mod_token(it.id)
            parts.append(self._prefer_game_root_token(tok))

        # custom (non-Steam) mods
        for name in cfg.active.custom_mods.mods:
            tok = self._mod_token(name)
            parts.append(self._prefer_game_root_token(tok))

        # OCAP (if user chose link_to == "mods")
        oc = cfg.active.ocap
        if oc.enabled and oc.link_to == "mods":
            tok = self._mod_token(oc.link_name)
            parts.append(self._prefer_game_root_token(tok))

        # de-dup, keep order
        seen = set()
        ordered = []
        for p in parts:
            if p and p not in seen:
                seen.add(p)
                ordered.append(p)
        return ";".join(ordered)

    def _mod_token(self, name: str) -> str:
        """
        Normalize a mod token for -mod/-serverMod:
          "123"  -> "@123"
          "@123" -> "@123"
        """
        s = str(name).strip()
        if not s:
            return s
        return s if s.startswith("@") else f"@{s}"
    
    def _build_servermod_arg(self, cfg) -> str:
        """
        Old-style: -serverMod=@id;@id;...
        Order from config list, optional OCAP if linked to servermods.
        """
        parts: List[str] = []

        for it in cfg.active.workshop.servermods:
            tok = self._mod_token(it.id)
            # servermods were mirrored to game-root too; if not, fall back to instance servermods path
            p = self.settings.arma_root / tok
            if p.exists():
                parts.append(tok)
            else:
                fallback = self.layout.inst_servermods / str(it.id)
                parts.append(str(fallback) if (fallback.exists() or fallback.is_symlink()) else tok)

        oc = cfg.active.ocap
        if oc.enabled and oc.link_to == "servermods":
            tok = self._mod_token(oc.link_name)
            parts.append(self._prefer_game_root_token(tok))

        # de-dup, keep order
        seen = set()
        ordered = []
        for p in parts:
            if p and p not in seen:
                seen.add(p)
                ordered.append(p)
        return ";".join(ordered)

    def _profiles_dir(self) -> Path:
        return self.layout.inst_config / "profiles"

    def start_server(self) -> int:
        cfg = self.cfg
        
        dlcs_n = len(cfg.active.dlcs)
        mods_n = len(cfg.active.workshop.mods)
        maps_n = len(cfg.active.workshop.maps)
        servermods_n = len(cfg.active.workshop.servermods)
        custom_mods_n = len(cfg.active.custom_mods.mods)
        custom_servermods_n = len(cfg.active.custom_mods.servermods)
        hc_n = int(cfg.active.headless_clients.count if cfg.active.headless_clients.enabled else 0)
        ocap = bool(cfg.active.ocap.enabled)

        log.info(
            "Plan: dlcs=%d mods=%d(+%d custom) maps=%d servermods=%d(+%d custom) hc=%d ocap=%s",
            dlcs_n, mods_n, custom_mods_n, maps_n, servermods_n, custom_servermods_n, hc_n, ocap
        )
        log.info("Plan mods: %s", [f"{m.name or 'UNKNOWN'} ({m.id})" for m in cfg.active.workshop.mods])
        
        self.layout.inst_config.mkdir(parents=True, exist_ok=True)
        generate_server_cfg(cfg, self._server_cfg_path())

        profiles = self._profiles_dir()
        profiles.mkdir(parents=True, exist_ok=True)
        generate_profile_cfg(cfg, profiles, cfg.config_name)
        server_log = self.layout.inst_logs / "server.log"

        cmd = [
            str(self.settings.arma_binary),
            f"-port={cfg.server.port}",
            f"-config={self._server_cfg_path()}",
            f"-profiles={profiles}",
            f"-name={cfg.config_name}",
            f"-mod={self._build_mod_arg(cfg)}",
            f"-serverMod={self._build_servermod_arg(cfg)}",
        ] + cfg.runtime.extra_args

        self.runner.start("server", cmd, cwd=self.settings.arma_root, log_file=server_log)

        hc_cfg = cfg.active.headless_clients
        if hc_cfg.enabled and hc_cfg.count > 0:
            for i in range(1, hc_cfg.count + 1):
                hc_log = self.layout.inst_logs / f"hc-{i}.log"
                hc_cmd = [
                    str(self.settings.arma_binary),
                    "-client",
                    "-connect=127.0.0.1",
                    f"-port={cfg.server.port}",
                    f"-password={hc_cfg.password}",
                    f"-profiles={profiles / f'hc-{i}'}",
                    f"-name=hc-{i}",
                    f"-mod={self._build_mod_arg(cfg)}",
                ] + hc_cfg.extra_args
                self.runner.start(f"hc-{i}", hc_cmd, cwd=self.settings.arma_root, log_file=hc_log)

        server_proc = next(h.proc for h in self.runner.handles if h.name == "server")
        rc = server_proc.wait()
        log.info("Server exited with rc=%s", rc)
        self.runner.stop_all()
        return int(rc if rc is not None else 0)

    def stop(self) -> None:
        self.runner.stop_all()

    def status(self) -> dict:
        return self.runner.status()

from __future__ import annotations
from pathlib import Path
from .settings import Settings
from .logging_setup import get_logger
from .fs_layout import build_layout, ensure_dirs
from .config_loader import load_config
from .steamcmd import SteamCMD
from .content_manager import ContentManager
from .cfg_generator import generate_server_cfg
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
        
        p = self.plan()
        log.info( "Plan: dlcs=%d mods=%d maps=%d servermods=%d hc=%s ocap=%s", len(p.dlcs), len(p.workshop_mods), len(p.workshop_maps), len(p.workshop_servermods), p.headless_count, p.ocap_enabled )
        log.info( "Plan mods: %s", [m.id for m in p.workshop_mods])
        
        cm.ensure_dlcs(cfg.active.dlcs, validate=cfg.active.steam.force_validate, dry_run=dry_run)
        cm.ensure_workshop(cfg, dry_run=dry_run)
        cm.link_instance_content(cfg, dry_run=dry_run)

    def generate_server_cfg(self, *, dry_run: bool = False) -> Path:
        out = self.settings.arma_root / "config" / "generated_a3server.cfg"
        if dry_run:
            return out
        generate_server_cfg(self.cfg, out)
        return out

    def _build_mod_arg(self) -> str:
        parts = []
        for p in sorted(self.layout.inst_mods.iterdir()):
            if p.is_symlink() or p.is_dir():
                parts.append(str(p))
        return ";".join(parts)

    def _build_servermod_arg(self) -> str:
        parts = []
        for p in sorted(self.layout.inst_servermods.iterdir()):
            if p.is_symlink() or p.is_dir():
                parts.append(str(p))
        return ";".join(parts)

    def _profiles_dir(self) -> Path:
        return self.settings.arma_instance / self.cfg.server.profiles_subdir

    def start_server(self) -> int:
        cfg = self.cfg
        
        p = self.plan()
        log.info( "Plan: dlcs=%d mods=%d maps=%d servermods=%d hc=%s ocap=%s", len(p.dlcs), len(p.workshop_mods), len(p.workshop_maps), len(p.workshop_servermods), p.headless_count, p.ocap_enabled )
        log.info( "Plan mods: %s", [m.id for m in p.workshop_mods])
        
        profiles = self._profiles_dir()
        profiles.mkdir(parents=True, exist_ok=True)

        server_log = self.layout.inst_logs / "server.log"

        cmd = [
            str(self.settings.arma_binary),
            f"-port={cfg.server.port}",
            f"-config={self.settings.arma_root / 'config' / 'generated_a3server.cfg'}",
            f"-profiles={profiles}",
            f"-name={cfg.config_name}",
            f"-mod={self._build_mod_arg()}",
            f"-serverMod={self._build_servermod_arg()}",
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
                    f"-mod={self._build_mod_arg()}",
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

"""
server.py — Launches the Arma 3 dedicated server and headless clients
---------------------------------------------------------------------
Builds startup parameters, handles config injection for HCs,
and starts all server processes with logging and error handling.
"""

import os
import re
import subprocess
import threading
from string import Template
from pathlib import Path
import logging
import time
# Use explicit logger name so setup_logger configures it predictably.
# setup_logger(...) should configure "arma_launcher" (see __main__.py).
logger = logging.getLogger("arma_launcher")


class ServerLauncher:
    def __init__(self, config, mods):
        self.cfg = config
        self.mods = mods

        self.arma_binary = os.getenv("ARMA_BINARY", "/arma3/arma3server_x64")
        self.limit_fps = self.cfg.limit_fps
        self.world = self.cfg.world
        self.port = self.cfg.port
        self.profile = self.cfg.profile
        self.clients = self.cfg.headless_clients
        self.basic_cfg = self.cfg.common_share / self.cfg.basic_config
        self.param_cfg = self.cfg.config_dir / self.cfg.param_config
        self.server_cfg = self.cfg.config_dir / self.cfg.arma_config

    # ---------------------------------------------------------------------- #
    def start(self):
        """Main entrypoint: prepare and launch server and HCs."""
        logger.info("Preparing Arma server launch parameters...")
        launch_cmd = self._build_server_command()

        if self.clients > 0:
            logger.info(f"Configured to start {self.clients} headless client(s).")
            self._start_headless_clients(launch_cmd)

        logger.info("Starting Arma 3 dedicated server...")
        logger.debug(f"Full launch command:\n{launch_cmd}")

        return_code = launch_with_live_logging(launch_cmd,
                                       stdout_log="/arma3/logs/arma_server.log",
                                       stderr_log="/arma3/logs/arma_server_errors.log")
        while(True):
            time.sleep(1)

    # ---------------------------------------------------------------------- #
    def _build_server_command(self) -> str:
        """Build the full Arma 3 server launch command."""
        mods_param = self._mod_param("mod", self.cfg.mods_dir)
        servermods_param = self._mod_param("serverMod", self.cfg.servermods_dir)

        launch = f"{self.arma_binary} -filePatching -limitFPS={self.limit_fps} -world={self.world}"
        launch += f" -port={self.port} -name=\"{self.profile}\" -profiles=\"/arma3/config/profiles\""
        launch += f" {mods_param} {servermods_param}"

        # Add base and param configs if present
        if self.basic_cfg.exists():
            launch += f" -cfg=\"{self.basic_cfg}\""
        if self.param_cfg.exists():
            with open(self.param_cfg) as f:
                extra_params = f.readline().strip()
                launch += f" {extra_params}"
        if self.server_cfg.exists():
            launch += f" -config=\"{self.server_cfg}\""

        return launch

    # ---------------------------------------------------------------------- #
    def _mod_param(self, name: str, path: Path) -> str:
        """Generate mod launch parameter string."""
        if not path.exists():
            return ""
        mods = [str(m) for m in path.iterdir() if m.is_dir() and m.name.startswith("@")]
        if not mods:
            return ""
        joined = ";".join(mods)
        return f' -{name}="{joined}" '

    # ---------------------------------------------------------------------- #
    def _start_headless_clients(self, server_cmd: str):
        """Start configured number of headless clients (HCs)."""
        tmp_cfg = Path("/tmp/arma3.cfg")

        logger.info("Preparing temporary headless client config...")
        try:
            data = self.server_cfg.read_text()
            matches = re.findall(r'(\w+\[\])\s*=\s*\{(.*?)\};', data, re.MULTILINE)
            config_values = {m[0].lower(): m[1] for m in matches}

            if "headlessclients[]" not in config_values:
                data += '\nheadlessclients[] = {"127.0.0.1"};\n'
            if "localclient[]" not in config_values:
                data += '\nlocalclient[] = {"127.0.0.1"};\n'

            tmp_cfg.write_text(data)
        except Exception as e:
            logger.error(f"Failed to prepare temporary config for HCs: {e}")
            return

        base_launch = (
            f"{server_cmd} -client -connect=127.0.0.1 -port={self.port}"
            f" -config=\"{tmp_cfg}\""
        )

        for i in range(self.clients):
            hc_template = Template(os.getenv("HEADLESS_CLIENTS_PROFILE", "$profile-hc-$i"))
            hc_name = hc_template.substitute(profile=self.profile, i=i, ii=i + 1)

            hc_launch = f"{base_launch} -name=\"{hc_name}\""
            logger.info(f"Launching headless client {i+1}/{self.clients}: {hc_name}")
            logger.debug(f"HC Command: {hc_launch}")

            subprocess.Popen(hc_launch, shell=True)

    # Ende Klasse ServerLauncher


def stream_reader(pipe, logger_func, log_file=None, filters=None):
    """
    Reads output from a subprocess pipe and routes it to logger and/or file.
    Runs in its own thread.
    """
    # open file with explicit encoding and line-buffering if requested
    if log_file:
        try:
            log_fh = open(log_file, "a", buffering=1, encoding="utf-8")
        except OSError:
            logger.exception(f"Cannot open log file {log_file} for appending")
            log_fh = None
    else:
        log_fh = None

    try:
        for line in iter(pipe.readline, ""):
            if not line:
                continue
            line = line.rstrip("\n")
            # Filter if needed
            if filters and not any(f.lower() in line.lower() for f in filters):
                continue
            logger_func(line)
            if log_fh:
                log_fh.write(line + "\n")
    except Exception:
        logger.exception("Error while reading process stream")
    finally:
        if log_fh:
            log_fh.close()
        try:
            pipe.close()
        except Exception:
            pass


def launch_with_live_logging(command, stdout_log=None, stderr_log=None):
    """
    Launch Arma 3 server process with live logging and optional file routing.
    """
    logger.info("Launching Arma 3 server with live logging...")
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # line-buffered
    )

    # Create threads for live log streaming
    t_out = threading.Thread(
        target=stream_reader,
        args=(process.stdout, logger.info, stdout_log),
        daemon=True,
    )
    t_err = threading.Thread(
        target=stream_reader,
        args=(process.stderr, logger.error, stderr_log, ["error", "warning"]),
        daemon=True,
    )
    t_out.start()
    t_err.start()

    process.wait()  # Block until Arma exits
    logger.info(f"Arma 3 server exited with code {process.returncode}")
    
    return process.returncode

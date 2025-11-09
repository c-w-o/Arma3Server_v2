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

# Create module-level patterns so both server and HCs can reuse them
SEP_PATTERNS = [
    r"does not support Extended Event Handlers",
    r"Warning Message: No entry 'bin\\config.bin/CfgWeapons/manual",
    r"Warning Message: '/' is not a value",
    r"Warning Message: Size: '/' not an array",
    r"Warning: rightHandIKCurve, wrong size",
    r"Warning: unset head bob mode in animation",
    r"doesn't exist in skeleton OFP2_ManSkeleton",
    r"Error: Object\(2 :",
    r"Warning: Convex component representing",
    r"does not support Extended Event Handlers! Addon:",
    r"Updating base class ->",
]
SEP_LOG_PATH = "/arma3/logs/arma_cba_warnings.log"

# precompile regexes once at module import time to avoid per-line compile/errors
SEP_REGEXES = []
for _pat in SEP_PATTERNS:
    try:
        SEP_REGEXES.append(re.compile(_pat, re.IGNORECASE))
    except re.error:
        logger.exception(f"Invalid regex in SEP_PATTERNS, skipping: {_pat}")

# keep track of patterns that already raised so we don't spam the logs
BAD_SEP_PATTERNS_LOGGED = set()
_BAD_SEP_LOCK = threading.Lock()


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

        # keep references to started headless client processes (optional shutdown/monitoring)
        self.hc_procs = []

    # ---------------------------------------------------------------------- #
    def start(self):
        """Main entrypoint: prepare and launch server and HCs."""
        logger.info("Preparing Arma server launch parameters...")
        params = self._build_server_command()

        # build HC params snapshot (before server-specific -config is applied)
        hc_params = dict(params)

        if self.clients > 0:
            logger.info(f"Configured to start {self.clients} headless client(s).")
            self._start_headless_clients(hc_params)

        # If there's a server-specific config file, add/override it in params
        if self.server_cfg.exists():
            params["config"] = str(self.server_cfg)

        launch_cmd = self._params_to_cmd(params)
        logger.info("Starting Arma 3 dedicated server...")
        logger.debug(f"Full launch command:\n{launch_cmd}")

        return_code = launch_with_live_logging(
            launch_cmd,
            stdout_log="/arma3/logs/arma_server.log",
            stderr_log="/arma3/logs/arma_server_errors.log",
        )
        # return the process return code (no infinite loop)
        return return_code

    # ---------------------------------------------------------------------- #
    def _build_server_command(self) -> dict:
        """Build the server launch parameters as a dict (key -> value)."""
        
        
                
                
        mods = self._mod_param("mod", self.cfg.mods_dir)
        servermods = self._mod_param("serverMod", self.cfg.servermods_dir)
        merged_cfg=self.cfg.get_merged_config()
        logger.debug(f"{merged_cfg}")
        for cdlc, active in merged_cfg.get("dlcs", {}).items():
            if cdlc == "contact":
                if active:
                    dlc_short=self.cfg.bi_key_map[cdlc]
                    mods = str(dlc_short) + (";" + mods if len(mods) > 0 else "")
                continue
            if not cdlc in self.cfg.dlc_key_map:
                logger.warning(f"CDLC {cdlc} unknown or not found, cannot resolve short name")
            if active:
                dlc_short=self.cfg.dlc_key_map[cdlc]
                mods = str(dlc_short) + (";" + mods if len(mods) > 0 else "")
                    
        params = {}
        if getattr(self.cfg, "filePatching", False):
            params["filePatching"] = True

        params["limitFPS"] = str(self.limit_fps)
        params["world"] = self.world
        params["port"] = str(self.port)
        params["name"] = self.profile
        params["profiles"] = "/arma3/config/profiles"

        if mods:
            params["mod"] = mods
        if servermods:
            params["serverMod"] = servermods

        # Add base and param configs if present
        if self.basic_cfg.exists():
            params["cfg"] = str(self.basic_cfg)
        if self.param_cfg.exists():
            with open(self.param_cfg) as f:
                extra_params = f.readline().strip()
                if extra_params:
                    params["extra"] = extra_params

        return params

    # ---------------------------------------------------------------------- #
    def _params_to_cmd(self, params: dict) -> str:
        """
        Convert params dict to a shell command string.
        Rules:
         - If a key already starts with '-', use it verbatim as flag name; otherwise prefix with '-'
         - Boolean True -> emit flag alone (e.g. -filePatching or -client)
         - None  -> emit flag alone (treat as "only the parameter key / flag")
         - Strings -> emit -key=value; for specific keys value will be quoted
         - 'extra' -> appended verbatim at the end
        """
        params_local = dict(params)  # do not mutate caller dict
        parts = [self.arma_binary]

        # handle filePatching boolean (may be keyed as 'filePatching' or '-filePatching')
        if params_local.pop("filePatching", False) or params_local.pop("-filePatching", False):
            parts.append("-filePatching")

        # helper to resolve key variants and produce flag name (+quote rules)
        def flag_for(key):
            return key if key.startswith("-") else f"-{key}"

        def needs_quote(stripped_key):
            return stripped_key in {"name", "profiles", "cfg", "config", "mod", "serverMod", "password"}

        # deterministic order for common params
        ordered = ["limitFPS", "world", "port", "name", "profiles", "mod", "serverMod", "cfg", "config", "connect", "client", "password", "extra"]
        handled = set()

        for k in ordered:
            # accept both 'k' and '-k' forms
            val = None
            used_key = None
            if k in params_local:
                val = params_local[k]; used_key = k
            elif f"-{k}" in params_local:
                val = params_local[f"-{k}"]; used_key = f"-{k}"
            if used_key is None:
                continue
            handled.add(used_key)
            # build flag
            flag = flag_for(used_key)
            stripped = used_key.lstrip("-")

            # Treat None as "flag only" (emit -key)
            if val is None:
                parts.append(flag)
                continue

            if isinstance(val, bool):
                if val:
                    parts.append(flag)
                # false -> skip
            else:
                sval = str(val)
                if stripped == "extra":
                    parts.append(sval)
                else:
                    if needs_quote(stripped):
                        parts.append(f'{flag}="{sval}"')
                    else:
                        parts.append(f"{flag}={sval}")

        # any remaining params (not in ordered) get appended (respect leading dash if present)
        for k, v in params_local.items():
            if k in handled:
                continue
            flag = flag_for(k)
            stripped = k.lstrip("-")

            # Treat None as "flag only"
            if v is None:
                parts.append(flag)
                continue

            if isinstance(v, bool):
                if v:
                    parts.append(flag)
            else:
                sval = str(v)
                if stripped == "extra":
                    parts.append(sval)
                elif stripped in {"name", "profiles", "cfg", "config", "mod", "serverMod", "password"}:
                    parts.append(f'{flag}="{sval}"')
                else:
                    parts.append(f"{flag}={sval}")

        return " ".join(parts)

    # ---------------------------------------------------------------------- #
    def _mod_param(self, name: str, path: Path) -> str:
        """Return semicolon-separated mod list (without -name=) or empty string."""
        if not path.exists():
            return ""
        mods = []
        for m in path.iterdir():
            if not (m.is_dir() and m.name.startswith("@")):
                continue
            try:
                # wenn der Mod-Pfad unter dem arma_root liegt, entferne das Präfix
                rel = m.relative_to(self.cfg.arma_root)
                mods.append(rel.as_posix())
            except Exception:
                # sonst kompletten Pfad verwenden (als POSIX-String)
                mods.append(m.as_posix())
        if not mods:
            return ""
        return ";".join(mods)

    # ---------------------------------------------------------------------- #
    def _start_headless_clients(self, base_params: dict):
        """Start configured number of headless clients (HCs). Builds HC start strings from params dict."""
        
        hd_pass = self.cfg.server_password
        for i in range(self.clients):
            # per-HC params: copy base, then set client/connect/port/config/name/password
            hc_params = dict(base_params)

            # remove serverMod for headless clients (accept both forms)
            hc_params.pop("serverMod", None)
            hc_params.pop("-serverMod", None)

            hc_params["client"] = None
            hc_params["connect"] = "127.0.0.1"
            hc_params["port"] = str(self.port)
            # keep same config reference as original behavior (filename)
            hc_params["config"] = str(self.cfg.arma_config)
            # per-HC name
            hc_template = Template(os.getenv("HEADLESS_CLIENTS_PROFILE", "$profile-hc-$i"))
            hc_name = hc_template.substitute(profile=self.profile, i=i, ii=i + 1)
            hc_params["name"] = hc_name
            hc_params["password"] = hd_pass

            hc_launch = self._params_to_cmd(hc_params)
            logger.info(f"Launching headless client {i+1}/{self.clients}: {hc_name}")
            logger.debug(f"HC Command: {hc_launch}")

            # start HC with captured stdout/stderr so we can route logs separately
            proc = subprocess.Popen(
                hc_launch,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            # per-HC logger (will inherit global logging config)
            hc_logger = logging.getLogger(f"arma_launcher.hc.{i+1}")
            hc_out_log = f"/arma3/logs/headless_client_{i+1}.log"
            hc_err_log = f"/arma3/logs/headless_client_{i+1}_err.log"

            t_hc_out = threading.Thread(
                target=stream_reader,
                args=(proc.stdout, hc_logger.info, hc_out_log),
                kwargs={"prefix": hc_name},
                daemon=True,
            )
            t_hc_err = threading.Thread(
                target=stream_reader,
                args=(proc.stderr, hc_logger.error, hc_err_log, ["error", "warning"], SEP_REGEXES, SEP_LOG_PATH),
                kwargs={"prefix": hc_name},
                daemon=True,
            )
            t_hc_out.start()
            t_hc_err.start()
            # keep process reference for later monitoring/shutdown if desired
            self.hc_procs.append((proc, hc_name))

            # optional small throttle between HC starts
            try:
                time.sleep(float(os.getenv("HC_START_DELAY", "1")))
            except Exception:
                pass

    # Ende Klasse ServerLauncher


def stream_reader(pipe, logger_func, log_file=None, filters=None, separate_patterns=None, separate_log=None, prefix=None):
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

    if separate_log:
        try:
            sep_fh = open(separate_log, "a", buffering=1, encoding="utf-8")
        except OSError:
            logger.exception(f"Cannot open separate log file {separate_log} for appending")
            sep_fh = None
    else:
        sep_fh = None

    try:
        for line in iter(pipe.readline, ""):
            # EOF -> break
            if line == "":
                break
            line = line.rstrip("\n")

            # If separate_patterns configured and line matches -> write to separate log and skip main logging
            if separate_patterns:
                try:
                    # support compiled regex objects or plain string patterns (backwards compatible)
                    matched = any(
                        (pat.search(line) if hasattr(pat, "search") else re.search(pat, line, re.IGNORECASE))
                        for pat in separate_patterns
                    )
                    if matched:
                        out_line = f"[{prefix}] {line}" if prefix else line
                        if sep_fh:
                            sep_fh.write(out_line + "\n")
                            try:
                                sep_fh.flush()
                            except Exception:
                                pass
                        # do not forward to main logger
                        continue
                except Exception:
                    # Diagnose which pattern fails, but log each failing pattern only once to avoid flooding
                    try:
                        with _BAD_SEP_LOCK:
                            for pat in separate_patterns:
                                if pat in BAD_SEP_PATTERNS_LOGGED:
                                    continue
                                try:
                                    if hasattr(pat, "search"):
                                        # compiled regex -> try a single search
                                        pat.search(line)
                                    else:
                                        # string pattern -> try re.search
                                        re.search(pat, line, re.IGNORECASE)
                                except Exception as e:
                                    BAD_SEP_PATTERNS_LOGGED.add(pat)
                                    logger.exception(f"separate_patterns element raised for pattern: {repr(pat)}; will not repeat this message")
                    except Exception:
                        logger.debug("Error diagnosing separate_patterns failure")
                    # keep a single low-volume debug note for this line
                    logger.debug("Error while applying separate_patterns; continuing normal logging")

            # Filter if needed
            if filters and not any(f.lower() in line.lower() for f in filters):
                continue

            out_line = f"[{prefix}] {line}" if prefix else line
            logger_func(out_line)
            if log_fh:
                log_fh.write(out_line + "\n")
    except Exception:
        logger.exception("Error while reading process stream")
    finally:
        if log_fh:
            log_fh.close()
        if sep_fh:
            try:
                sep_fh.close()
            except Exception:
                pass
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
        args=(process.stderr, logger.error, stderr_log, ["error", "warning"], SEP_REGEXES, SEP_LOG_PATH),
        daemon=True,
    )
    t_out.start()
    t_err.start()

    process.wait()  # Block until Arma exits
    logger.info(f"Arma 3 server exited with code {process.returncode}")
    
    return process.returncode

"""
steam.py — SteamCMD management for Arma 3 Workshop
---------------------------------------------------
Handles SteamCMD execution, login, retries, and mod downloads.
"""

import os
import time
import subprocess
import re
import json
from datetime import datetime
from pathlib import Path
from arma_launcher.log import get_logger
from contextlib import contextmanager

logger = get_logger()


class SteamCMD:
    def __init__(self, config):
        self.cfg = config
        self.steam_root = Path("/steamcmd")
        self.tmp_dir = self.cfg.tmp_dir
        self.workshop_dir = self.tmp_dir / "steamapps/workshop/content/107410"
        self.user = config.steam_user
        self.password = config.steam_password

    # --- Datei-basierter plattformübergreifender Mutex für steamcmd ---
    def _lock_file_path(self) -> Path:
        return Path(self.tmp_dir) / "steamcmd.lock"

    @contextmanager
    def _steamcmd_mutex(self, timeout: int = 600):
        """
        Acquire a filesystem lock to serialize steamcmd invocations across processes.
        Uses fcntl on POSIX and msvcrt on Windows. Waits up to `timeout` seconds.
        """
        lock_path = self._lock_file_path()
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        # open in append-binary so file exists and we can lock
        lock_file = open(lock_path, "a+b")
        start = time.time()
        try:
            if os.name == "nt":
                import msvcrt
                while True:
                    try:
                        # lock 1 byte (non-blocking)
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError:
                        if time.time() - start > timeout:
                            raise TimeoutError("Timeout acquiring steamcmd lock")
                        time.sleep(0.1)
            else:
                import fcntl
                while True:
                    try:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except (BlockingIOError, OSError):
                        if time.time() - start > timeout:
                            raise TimeoutError("Timeout acquiring steamcmd lock")
                        time.sleep(0.1)
            logger.debug(f"Acquired steamcmd lock: {lock_path}")
            yield
        finally:
            try:
                if os.name == "nt":
                    try:
                        lock_file.seek(0)
                        import msvcrt
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    except Exception:
                        pass
                else:
                    try:
                        import fcntl
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    except Exception:
                        pass
            finally:
                lock_file.close()
                logger.debug(f"Released steamcmd lock: {lock_path}")
    # --- Ende Mutex ---

    def _mask_cmd(self, cmd):
        """
        Return a masked copy of cmd where username/password after '+login' are replaced.
        """
        tokens = list(map(str, cmd))
        for idx, t in enumerate(tokens):
            if t == "+login":
                if idx + 1 < len(tokens):
                    tokens[idx + 1] = "<REDACTED_USER>"
                if idx + 2 < len(tokens) and not tokens[idx + 2].startswith("+"):
                    tokens[idx + 2] = "<REDACTED_PW>"
                break
        return tokens

    def _steamcmd_run(self, cmd, filter_array=None, retries: int = 5, sleep_seconds: int = 60, per_try_timeout: int = 30) -> bool:
        """
        Common runner for steamcmd invocations.
        Streams output, applies filters, detects rate-limits/timeouts and performs retries with backoff.
        Returns True on success (exitcode 0), False otherwise.
        """
        
        if filter_array is None:
            filter_array = [
                "Redirecting stderr to",
                "ILocalize::AddFile()",
                "WARNING: setlocale(",
                "Logging directory:",
                "UpdateUI: ",
                "Restarting steamcmd by",
                "Steam Console Client ",
                "type 'quit'",
                "Loading Steam API",
                "Logging in using",
                "Logging in user",
                "Waiting for client config",
                "aiting for user info",
            ]
        
        filter_array = filter_array or []

        # gesamter Aufruf durch Mutex serialisieren (verhindert parallele steamcmd-Starts)
        try:
            with self._steamcmd_mutex():
                for attempt in range(1, retries + 1):
                    masked_cmd = self._mask_cmd(cmd)
                    logger.info(f"SteamCMD attempt {attempt}/{retries}: {' '.join(masked_cmd)}")
                    try:
                        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1) as proc:
                            try:
                                for line in proc.stdout:
                                    output = line.rstrip("\n")
                                    # skip noisey lines
                                    if any(m in output for m in filter_array):
                                        continue

                                    # progress/info routing
                                    if "Downloading update" in output or "Extracting" in output or "Success" in output:
                                        logger.info(output)
                                    else:
                                        logger.debug(output)

                                    # transient errors -> kill and retry
                                    if self._is_rate_limited(output):
                                        logger.warning("SteamCMD rate limited — killing process and retrying after backoff.")
                                        try:
                                            proc.kill()
                                        except Exception:
                                            pass
                                        break
                                    if self._is_timeout(output):
                                        logger.warning("SteamCMD timeout detected — killing process and retrying after backoff.")
                                        try:
                                            proc.kill()
                                        except Exception:
                                            pass
                                        break
                                    if self._is_request_revoked(output):
                                        logger.warning("SteamCMD login revoked / result 26 detected — killing process and retrying after backoff.")
                                        try:
                                            proc.kill()
                                        except Exception:
                                            pass
                                        break

                                # Wait for process to exit (guard with timeout)
                                try:
                                    returncode = proc.wait(timeout=per_try_timeout)
                                except subprocess.TimeoutExpired:
                                    logger.warning("SteamCMD did not exit in time — killing and treating as failure for this attempt.")
                                    try:
                                        proc.kill()
                                    except Exception:
                                        pass
                                    returncode = proc.wait()

                                if returncode == 0:
                                    logger.info("SteamCMD finished successfully.")
                                    return True
                                else:
                                    logger.debug(f"SteamCMD exited with code {returncode} (attempt {attempt}).")
                            except Exception as e:
                                logger.exception(f"Error while running SteamCMD: {e}")
                                try:
                                    proc.kill()
                                except Exception:
                                    pass
                    except FileNotFoundError:
                        logger.error("steamcmd executable not found at %s", self.steam_root)
                        return False
                    except Exception as e:
                        logger.exception(f"Failed to start SteamCMD: {e}")

                    # exponential backoff (capped)
                    backoff = min(sleep_seconds * (2 ** (attempt - 1)), 600)
                    logger.info(f"Waiting {backoff}s before next SteamCMD attempt.")
                    time.sleep(backoff)
        except TimeoutError as e:
            logger.error(f"Could not acquire steamcmd lock: {e}")
            return False

        logger.error("SteamCMD failed after all retries.")
        return False

    # ---------------------------------------------------------------------- #
    def download_mod(self, steam_id: str, name: str, path: str, retries: int = 5, sleep_seconds: int = 60) -> bool:
        """
        Downloads or updates a mod from Steam Workshop using SteamCMD.
        Uses shared runner to execute steamcmd and then ensures a symlink from mods dir -> workshop content.
        """

        cmd = [
            str(self.steam_root / "steamcmd.sh"),
            "+force_install_dir", str(self.tmp_dir),
            "+login", self.user, self.password,
            "+workshop_download_item", "107410", str(steam_id), "validate",
            "+quit",
        ]

        success = self._steamcmd_run(cmd, retries=retries, sleep_seconds=sleep_seconds)
        if not success:
            logger.error(f"Failed to download mod {steam_id} ({name}).")
            return False

        # ensure workshop source exists and create symlink at desired path
        src_path = self.workshop_dir / str(steam_id)
        dst_path = Path(path)
        if not src_path.exists():
            logger.warning(f"Workshop content not found after download: {src_path}")
            return False

        # --- NEU: minimale Datei-/Ordner-Prüfung ---
        try:
            if not self._verify_mod_minimum(src_path, name):
                logger.error(f"Mod {steam_id} ({name}) fehlt minimale Dateien/Ordner in {src_path}. Abbruch.")
                return False
        except Exception as e:
            logger.exception(f"Fehler bei der Validierung von {src_path}: {e}")
            return False
        # --- Ende Prüfung ---

        try:
            dst_parent = dst_path.parent
            dst_parent.mkdir(parents=True, exist_ok=True)
            # remove existing destination if it's a broken symlink or file
            if dst_path.exists() or dst_path.is_symlink():
                try:
                    if dst_path.is_dir() and not dst_path.is_symlink():
                        logger.debug(f"Destination exists and is a real dir, leaving it: {dst_path}")
                    else:
                        dst_path.unlink()
                except Exception:
                    logger.debug(f"Could not remove existing destination {dst_path}")
            # create symlink pointing to workshop content
            if not dst_path.exists():
                try:
                    os.symlink(str(src_path), str(dst_path))
                    logger.info(f"Linked {dst_path} -> {src_path}")
                except FileExistsError:
                    logger.debug(f"Symlink already exists: {dst_path}")
                except OSError as e:
                    logger.warning(f"Failed to create symlink {dst_path} -> {src_path}: {e}")
        except Exception as e:
            logger.exception(f"Error while linking mod {steam_id}: {e}")

        # write local metadata timestamp
        try:
            remote_dt = self.get_last_update_date(steam_id)
            if remote_dt:
                self.set_local_update_time(dst_path, steam_id, name, remote_dt)
        except Exception:
            logger.debug("Ignoring failure to set local update time.")

        return True

    def install_arma(self, install_dir: str = None, retries: int = 3, sleep_seconds: int = 30) -> bool:
        """
        Install or update Arma 3 (app 233780) via SteamCMD.
        """
        install_dir = install_dir or str(self.cfg.arma_root)
        cmd_normal = [
            str(self.steam_root / "steamcmd.sh"),
            "+force_install_dir", str(install_dir),
            "+login", self.user, self.password,
            "+app_update", "233780", "validate",
            "+quit",
        ]
        cmd_creator = [
            str(self.steam_root / "steamcmd.sh"),
            "+force_install_dir", str(install_dir),
            "+login", self.user, self.password,
            "+app_update", "233780", "-beta",
            "creatordlc", "validate",
            "+quit"
        ]
        cmd_contact = [
            str(self.steam_root / "steamcmd.sh"),
            "+force_install_dir", str(install_dir),
            "+login", self.user, self.password,
            "+app_update", "233780", "-beta",
            "contact", "validate",
            "+quit"
        ]
        cmd=[]
        if self.cfg.needs_contact:
            logger.info("Validating contact arma3 dedicated server")
            cmd=cmd_contact
        elif self.cfg.needs_creator:
            logger.info("Validating creator arma3 dedicated server")
            cmd=cmd_creator
        else:
            logger.info("Validating vanilla arma3 dedicated server")
            cmd=cmd_normal
        logger.info(f"Installing/updating Arma 3 to {install_dir}")
        return self._steamcmd_run(cmd, retries=retries, sleep_seconds=sleep_seconds)

    def install_app(self, appid: str, install_dir: str = None, retries: int = 3, sleep_seconds: int = 30) -> bool:
        """
        Generic app installer (useful for DLCs via appid).
        """
        install_dir = install_dir or str(self.tmp_dir)
        cmd = [
            str(self.steam_root / "steamcmd.sh"),
            "+force_install_dir", str(install_dir),
            "+login", self.user, self.password,
            "+app_update", str(appid), "validate",
            "+quit",
        ]
        logger.info(f"Installing/updating app {appid} to {install_dir}")
        return self._steamcmd_run(cmd, filter_array=[], retries=retries, sleep_seconds=sleep_seconds)

    # ---------------------------------------------------------------------- #
    @staticmethod
    def _is_rate_limited(output: str) -> bool:
        return "Rate Limit Exceeded" in output or "HTTP 429" in output

    @staticmethod
    def _is_timeout(output: str) -> bool:
        return "Timeout" in output or "Failed to connect" in output

    @staticmethod
    def _is_request_revoked(output: str) -> bool:
        """
        Detect transient Steam auth/session revocation messages (e.g. 'result 26', 'Request revoked').
        Returns True when output contains known patterns that should trigger a retry.
        """
        if not output:
            return False
        o = output.lower()
        # common SteamCMD wording / variations
        patterns = [
            "result 26",
            "request revoked",
            "login result: 26",
            "disconnected from steam",
        ]
        return any(p in o for p in patterns)

    def get_local_update_time(self, mod_path):
        p = Path(mod_path) / ".modmeta.json"
        if not p.exists():
            return datetime.utcfromtimestamp(0)
        try:
            with p.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            ts = data.get("timestamp")
            if ts is None:
                return datetime.utcfromtimestamp(0)
            # timestamp stored as int epoch (UTC) or ISO string; try int first
            try:
                return datetime.utcfromtimestamp(int(ts))
            except Exception:
                try:
                    # fallback: ISO formatted string
                    return datetime.fromisoformat(str(ts))
                except Exception:
                    return datetime.utcfromtimestamp(0)
        except Exception:
            return datetime.utcfromtimestamp(0)
            
    def set_local_update_time(self, mod_path, steamid, name, dt):
        p = Path(mod_path) / ".modmeta.json"
        # normalize dt to an integer epoch (UTC) for JSON
        if isinstance(dt, datetime):
            ts = int(dt.replace(tzinfo=None).timestamp())
        else:
            try:
                ts = int(dt)
            except Exception:
                try:
                    ts = int(datetime.fromisoformat(str(dt)).timestamp())
                except Exception:
                    ts = int(datetime.utcnow().timestamp())

        data = {
            "steamid": steamid,
            "name": name,
            "timestamp": ts,
        }

        with p.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

    # ---------------------------------------------------------------------- #
    def get_last_update_date(self, steam_id: str):
        """
        Query Steam Web API (GetPublishedFileDetails) to get the last update timestamp.
        Falls das fehlschlägt, gibt None zurück.
        """
        import urllib.request
        import urllib.parse
        

        url = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
        post_data = urllib.parse.urlencode({
            "itemcount": "1",
            "publishedfileids[0]": str(steam_id),
        }).encode("utf-8")

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
            # time_updated is an epoch timestamp (UTC)
            return datetime.utcfromtimestamp(int(time_updated))
        except Exception as e:
            logger.debug(f"GetPublishedFileDetails failed for {steam_id}: {e}")
            return None

    def is_mod_up_to_date(self, steam_id: str, mod_path: str, name: str) -> bool:
        """
        Prüft, ob ein lokaler Mod aktuell ist:
        - minimale Datei-/Ordner-Prüfung (_verify_mod_minimum)
        - Vergleich lokaler .modmeta.json Timestamp mit letztem Remote-Update
        Rückgabe: True = aktuell / keine Aktion nötig, False = nicht aktuell (Download empfohlen).
        Wenn das Remote-Datum nicht ermittelt werden kann, wird False zurückgegeben (so wird beim Start ein erneuter Download ausgelöst).
        """
        dst = Path(mod_path)
        # lokale Existenz + minimale Validierung
        if not dst.exists():
            logger.info(f"Mod path does not exist: {dst}")
            return False
        try:
            if not self._verify_mod_minimum(dst, name):
                logger.info(f"Mod at {dst} failed minimum validation")
                return False
        except Exception as e:
            logger.exception(f"Validation error for {dst}: {e}")
            return False

        # lokale und remote Zeitstempel vergleichen
        local_dt = self.get_local_update_time(dst)
        remote_dt = self.get_last_update_date(steam_id)

        if remote_dt is None:
            logger.debug(f"Could not retrieve remote update date for {steam_id}; treating as not up-to-date.")
            return False

        # remote neuer -> not up-to-date
        if remote_dt > local_dt:
            logger.info(f"Mod {steam_id} at {dst} is outdated (remote {remote_dt} > local {local_dt})")
            return False

        logger.debug(f"Mod {steam_id} at {dst} is up-to-date.")
        return True

    def _verify_mod_minimum(self, src_path: Path, name: str,  required: list = None) -> bool:
        """
        Prüft, ob im heruntergeladenen Mod-Verzeichnis minimale Inhalte vorhanden sind.
        Standard: entweder vorhandener 'addons' Ordner, mindestens eine .pbo Datei oder 'meta.cpp'.
        Gebe True zurück wenn Mindestanforderungen erfüllt, sonst False.
        """
        if required is None:
            required = ["addons", "meta.cpp", ".pbo"]

        src = Path(src_path)
        if not src.exists():
            return False

        missing = []

        # Prüfe auf 'addons' Ordner
        if "addons" in required:
            if (src / "addons").exists():
                pass
            elif any(src.glob("**/*.pbo")):
                pass
            else:
                missing.append("addons or .pbo")

        # Prüfe auf meta.cpp
        if "meta.cpp" in required:
            if not (src / "meta.cpp").exists():
                # versuchen, case-insensitive zu finden
                found_meta = any(p.name.lower() == "meta.cpp" for p in src.rglob("*") if p.is_file())
                if not found_meta:
                    missing.append("meta.cpp")

        # zusätzliche benannte Anforderungen (falls übergeben)
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
            logger.debug(f"Validation failed for {name} ({src_path}). Missing: {missing}")
            return False
        return True

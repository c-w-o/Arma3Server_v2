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

logger = get_logger()


class SteamCMD:
    def __init__(self, config):
        self.cfg = config
        self.steam_root = Path("/steamcmd")
        self.tmp_dir = self.cfg.tmp_dir
        self.workshop_dir = self.tmp_dir / "steamapps/workshop/content/107410"
        self.user = config.steam_user
        self.password = config.steam_password

    def _steamcmd_run(self, cmd, filter_array=None, retries: int = 5, sleep_seconds: int = 60, per_try_timeout: int = 30) -> bool:
        """
        Common runner for steamcmd invocations.
        Streams output, applies filters, detects rate-limits/timeouts and performs retries with backoff.
        Returns True on success (exitcode 0), False otherwise.
        """
        
        if filter is None:
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
        for attempt in range(1, retries + 1):
            logger.info(f"SteamCMD attempt {attempt}/{retries}: {' '.join(map(str, cmd))}")
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
        Install or update Arma 3 (app 107410) via SteamCMD.
        """
        install_dir = install_dir or str(self.cfg.arma_root)
        cmd = [
            str(self.steam_root / "steamcmd.sh"),
            "+force_install_dir", str(install_dir),
            "+login", self.user, self.password,
            "+app_update", "233780", "validate",
            "+quit",
        ]
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

"""
steam.py — SteamCMD management for Arma 3 Workshop
---------------------------------------------------
Handles SteamCMD execution, login, retries, and mod downloads.
"""

import os
import time
import subprocess
import re
import select
from pathlib import Path
from arma_launcher.log import get_logger

logger = get_logger()


class SteamCMD:
    def __init__(self, config):
        self.cfg = config
        self.steam_root = Path("/steamcmd")
        self.tmp_dir = Path("/tmp")
        self.user = config.steam_user
        self.password = config.steam_password

    # ---------------------------------------------------------------------- #
    def download_mod(self, steam_id: str, name: str, path: str, retries: int = 5, sleep_seconds: int = 60) -> bool:
        """
        Downloads or updates a mod from Steam Workshop using SteamCMD.
        Includes retry logic for rate limits and connection issues.
        """
        
        filter_array=[
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
        
        cmd = [
            str(self.steam_root / "steamcmd.sh"),
            "+force_install_dir", path,
            "+login", self.user, self.password,
            "+workshop_download_item", "107410", str(steam_id), "validate",
            "+quit",
        ]
        
        logger.debug(f"STEAM CMD: {cmd}")

        for attempt in range(1, retries + 1):
            logger.info(f"Downloading mod attempt {attempt}/{retries} of {steam_id} - {name}...")
            try:
                with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1) as proc:
                    try:
                        
                        # Stream output and look for transient error signals.
                        for line in proc.stdout:
                            output = line.strip()
                            if any(m in output for m in filter_array):
                                pass
                            elif "Downloading update" in output:
                                with re.search(r'^\[\s*(\d{1,3}(?:\.\d+)?)%\]\s*.*\(\s*(\d+)\s+of\s+(\d+)\s+KB\s*\)', output) as m:
                                    logger.info(f"[{m.group(1)}%] ({m.group(2)} / {m.group(3)} KiB)\r")
                            
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

                        # Wait for process to exit (guard with timeout in case it hangs)
                        try:
                            returncode = proc.wait(timeout=30)
                        except subprocess.TimeoutExpired:
                            logger.warning("SteamCMD did not exit in time — killing and treating as failure for this attempt.")
                            try:
                                proc.kill()
                            except Exception:
                                pass
                            returncode = proc.wait()

                        if returncode == 0:
                            logger.info(f"Successfully downloaded/updated mod {steam_id} ({name}).")
                            return True
                        else:
                            logger.debug(f"SteamCMD exited with code {returncode} on attempt {attempt} for {steam_id}.")

                    except Exception as e:
                        logger.exception(f"Error while running SteamCMD for {steam_id}: {e}")
                        try:
                            proc.kill()
                        except Exception:
                            pass

            except FileNotFoundError:
                logger.error("steamcmd executable not found at %s", self.steam_root)
                break
            except Exception as e:
                logger.exception(f"Failed to start SteamCMD for {steam_id}: {e}")

            # exponential backoff (capped)
            backoff = min(sleep_seconds * (2 ** (attempt - 1)), 600)
            logger.info(f"Waiting {backoff}s before next attempt for {steam_id}.")
            time.sleep(backoff)

        logger.error(f"Failed to download mod {steam_id} after {retries} attempts.")
        return False

    # ---------------------------------------------------------------------- #
    @staticmethod
    def _is_rate_limited(output: str) -> bool:
        return "Rate Limit Exceeded" in output or "HTTP 429" in output

    @staticmethod
    def _is_timeout(output: str) -> bool:
        return "Timeout" in output or "Failed to connect" in output

    # ---------------------------------------------------------------------- #
    def get_last_update_date(self, steam_id: str):
        """
        Query Steam Web API (GetPublishedFileDetails) to get the last update timestamp.
        Falls das fehlschlägt, gibt None zurück.
        """
        import json
        import urllib.request
        import urllib.parse
        from datetime import datetime

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

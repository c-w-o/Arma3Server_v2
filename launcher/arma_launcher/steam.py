"""
steam.py — SteamCMD management for Arma 3 Workshop
---------------------------------------------------
Handles SteamCMD execution, login, retries, and mod downloads.
"""

import os
import time
import subprocess
import re
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
    def download_mod(self, steam_id: str, retries: int = 5, sleep_seconds: int = 60) -> bool:
        """
        Downloads or updates a mod from Steam Workshop using SteamCMD.
        Includes retry logic for rate limits and connection issues.
        """
        cmd = [
            str(self.steam_root / "steamcmd.sh"),
            "+force_install_dir", str(self.tmp_dir),
            "+login", self.user, self.password,
            "+workshop_download_item", "107410", str(steam_id), "validate",
            "+quit",
        ]

        for attempt in range(1, retries + 1):
            logger.info(f"Downloading mod {steam_id} (attempt {attempt}/{retries})...")
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            output = result.stdout

            if self._is_rate_limited(output):
                logger.warning("SteamCMD rate limited — sleeping for 3 minutes before retry.")
                time.sleep(180)
                continue
            if self._is_timeout(output):
                logger.warning("SteamCMD timeout detected — retrying in 60 seconds.")
                time.sleep(sleep_seconds)
                continue
            if result.returncode == 0:
                logger.info(f"Mod {steam_id} successfully downloaded or up-to-date.")
                return True

            logger.error(f"SteamCMD failed (code {result.returncode}) for mod {steam_id}")
            logger.debug(f"SteamCMD output:\n{output}")
            time.sleep(sleep_seconds)

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

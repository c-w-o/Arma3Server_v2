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
        Scrapes the Steam Workshop page for a given mod to find the last update time.
        """
        import ssl
        import urllib.request
        from datetime import datetime

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        url = f"https://steamcommunity.com/sharedfiles/filedetails/{steam_id}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                html = resp.read().decode(resp.headers.get_content_charset() or "utf-8")

            matches = re.findall(r'\"detailsStatRight\".*?>(.*?)<', html, re.MULTILINE)
            if len(matches) >= 2:
                try:
                    dt = datetime.strptime(matches[-1], "%d %b, %Y @ %I:%M%p")
                except ValueError:
                    dt = datetime.strptime(matches[-1], "%d %b @ %I:%M%p").replace(year=datetime.now().year)
                return dt
        except Exception as e:
            logger.error(f"Failed to retrieve update date for {steam_id}: {e}")

        return None

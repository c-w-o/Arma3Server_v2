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
            # spawn steamcmd and stream output for progress reporting
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            output_accum = []
            last_percent = None
            last_output_time = time.monotonic()
            NO_OUTPUT_TIMEOUT = 60  # seconds without any output -> assume interactive prompt / stuck
            try:
                # read with select so we can implement a no-output watchdog
                stdout = proc.stdout
                while True:
                    # check if process ended and no more data
                    if proc.poll() is not None:
                        # drain any remaining lines
                        for line in stdout:
                            line = line.rstrip("\n")
                            output_accum.append(line)
                        break

                    rlist, _, _ = select.select([stdout], [], [], 1.0)
                    if not rlist:
                        # no new data this second -> check watchdog
                        if (time.monotonic() - last_output_time) > NO_OUTPUT_TIMEOUT:
                            logger.error("SteamCMD produced no output for %s seconds after login — likely waiting for Steam Guard / interactive input. Aborting.", NO_OUTPUT_TIMEOUT)
                            # capture current accumulated output for debugging
                            try:
                                proc.kill()
                            except Exception:
                                pass
                            output = "\n".join(output_accum)
                            logger.debug("SteamCMD partial output:\n%s", output)
                            return False
                        continue

                    # data available
                    line = stdout.readline()
                    if line == "":
                        continue
                    line = line.rstrip("\n")
                    last_output_time = time.monotonic()
                    output_accum.append(line)

                    # detect interactive prompts that require user input (Steam Guard / 2FA / captcha)
                    low = line.lower()
                    if "steam guard" in low or "authentication code" in low or "code from the steam app" in low or "please enter the" in low and ("code" in low or "steam" in low):
                        logger.error("SteamCMD is asking for interactive authentication: %s", line)
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        return False

                    # look for percentage patterns like "12%" or "12.3 %"
                    m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", line)
                    if m:
                        percent = m.group(1)
                        # avoid spamming identical percents
                        if percent != last_percent:
                            logger.info(f"SteamCMD {steam_id} download: {percent}% — {line}")
                            last_percent = percent
                    else:
                        # generic progress/info lines
                        logger.debug(f"SteamCMD: {line}")

                output = "\n".join(output_accum)

                # detect common failure cases from accumulated output
                if self._is_rate_limited(output):
                    logger.warning("SteamCMD rate limited — sleeping for 3 minutes before retry.")
                    time.sleep(180)
                    continue
                if self._is_timeout(output):
                    logger.warning("SteamCMD timeout detected — retrying in 60 seconds.")
                    time.sleep(sleep_seconds)
                    continue

                if proc.returncode == 0:
                    logger.info(f"Mod {steam_id} successfully downloaded or up-to-date.")
                    return True
                else:
                    logger.error(f"SteamCMD failed (code {proc.returncode}) for mod {steam_id}")
                    logger.debug(f"SteamCMD output:\n{output}")
                    time.sleep(sleep_seconds)
            except Exception as e:
                logger.exception(f"Error while running SteamCMD for {steam_id}: {e}")
                try:
                    proc.kill()
                except Exception:
                    pass
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

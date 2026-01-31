from __future__ import annotations

import urllib.request
import urllib.parse
import json
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime, timedelta
from .logging_setup import get_logger

log = get_logger("arma.launcher.steam_metadata")

STEAM_API_URL = "https://steamcommunity.com/api/ISteamRemoteStorage/GetPublishedFileDetails/v1/"


class ModMetadataResolver:
    """Resolve mod metadata from local .modmeta.json files or Steam API."""
    
    def __init__(self, mod_paths: Dict[str, Path]):
        """
        Args:
            mod_paths: Dict of folder locations to search for .modmeta.json
                      e.g. {"mods": Path("/arma/mods"), "maps": Path("/arma/maps")}
        """
        self.mod_paths = mod_paths
    
    def _find_local_modmeta(self, mod_id: str) -> Optional[dict]:
        """Search for .modmeta.json file for a mod ID in all mod paths."""
        for folder_path in self.mod_paths.values():
            modmeta_path = folder_path / str(mod_id) / ".modmeta.json"
            if modmeta_path.exists():
                try:
                    data = json.loads(modmeta_path.read_text(encoding="utf-8"))
                    # Convert to our format
                    return {
                        "id": str(mod_id),
                        "name": data.get("name", f"Mod {mod_id}"),
                        "cached": True,  # Mark as from local cache
                        "source": "local"
                    }
                except Exception as e:
                    log.warning(f"Failed to read modmeta for {mod_id}: {e}")
        
        return None


def resolve_mod_ids(mod_ids: List[str], resolver: ModMetadataResolver) -> Dict[str, dict]:
    """
    Resolve mod IDs to names/metadata.
    
    Priority:
    1. Check local .modmeta.json files
    2. Fetch from Steam API for missing ones
    
    Returns dict: { "12345": {"id": "12345", "name": "Mod Name", "cached": True/False, "source": "local"/"steam"}, ... }
    """
    results = {}
    to_fetch = []
    
    # First: check local .modmeta.json files
    for mod_id in mod_ids:
        local_meta = resolver._find_local_modmeta(mod_id)
        if local_meta:
            results[str(mod_id)] = local_meta
        else:
            to_fetch.append(str(mod_id))
    
    # Second: fetch uncached from Steam API
    if to_fetch:
        log.info(f"Fetching {len(to_fetch)} mods from Steam API (not found locally)")
        try:
            batch_results = _fetch_from_steam(to_fetch)
            for mod_id, data in batch_results.items():
                results[str(mod_id)] = data
        except Exception as e:
            log.error(f"Failed to fetch mod metadata from Steam: {e}")
            # Fallback: create stub entries for uncached mods
            for mod_id in to_fetch:
                results[str(mod_id)] = {
                    "id": str(mod_id),
                    "name": f"Mod {mod_id}",
                    "error": "Failed to resolve name (not found locally or via Steam)",
                    "source": "fallback"
                }
    
    return results


def _fetch_from_steam(mod_ids: List[str]) -> Dict[str, dict]:
    """Fetch mod names from Steam API (max 100 per request)."""
    results = {}
    
    # Split into batches (Steam allows 100 per request)
    for i in range(0, len(mod_ids), 100):
        batch = mod_ids[i : i + 100]
        
        payload = {
            "itemcount": len(batch),
        }
        for idx, mod_id in enumerate(batch):
            payload[f"publishedfileids[{idx}]"] = str(mod_id)
        
        try:
            # Encode payload
            data = urllib.parse.urlencode(payload).encode("utf-8")
            
            # Create request with timeout
            req = urllib.request.Request(STEAM_API_URL, data=data)
            with urllib.request.urlopen(req, timeout=30) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
            
            if resp_data.get("response", {}).get("resultcount", 0) == 0:
                log.warning(f"No results from Steam for batch of {len(batch)} mods")
                continue
            
            for item in resp_data.get("response", {}).get("publishedfiledetails", []):
                file_id = str(item.get("publishedfileid", ""))
                if file_id:
                    results[file_id] = {
                        "id": file_id,
                        "name": item.get("title", f"Mod {file_id}"),
                        "cached": False,
                        "source": "steam"
                    }
        except urllib.error.URLError as e:
            log.error(f"Network error fetching mod batch from Steam: {e}")
        except Exception as e:
            log.error(f"Unexpected error fetching from Steam: {e}")
    
    return results



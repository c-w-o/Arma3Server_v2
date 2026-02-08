"""
Zentrale Merge-Logik für Defaults + Overrides.

Dies ist die kritische Komponente die Fehler aus config_loader.py
vermeiden sollte. Alle Merge-Operationen sind hier konzentriert
und können isoliert getestet werden.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
from copy import deepcopy

from ..models_file import (
    FileConfig_Defaults,
    FileConfig_Override,
    FileConfig_Mods,
    FileConfig_Dlcs,
    FileConfig_ModEntry,
    FileConfig_Mission,
    FileConfig_CustomMods,
)
from ..logging_setup import get_logger

log = get_logger("arma.config.merger")


class ConfigMerger:
    """
    Zentrale Merge-Logik für Konfigurationen.
    
    Strategie:
    - Defaults sind die Basis
    - Override ersetzen/ergänzen Defaults
    - Null/None = "behalte Default"
    - Leere Listen = "ersetze Default mit leer"
    """
    
    def merge(self, defaults: FileConfig_Defaults, override: FileConfig_Override) -> FileConfig_Defaults:
        """
        Merged Defaults mit Override zu einer kompletten Konfiguration.
        
        Args:
            defaults: Basis-Konfiguration
            override: Pro-Config Overrides
        
        Returns:
            Merged result (neue Instanz, keine Mutations)
        """
        result = deepcopy(defaults)
        
        # Merge primitives
        if override.maxPlayers is not None:
            result.maxPlayers = override.maxPlayers
        if override.hostname is not None:
            result.hostname = override.hostname
        if override.serverPassword is not None:
            result.serverPassword = override.serverPassword
        if override.adminPassword is not None:
            result.adminPassword = override.adminPassword
        if override.serverCommandPassword is not None:
            result.serverCommandPassword = override.serverCommandPassword
        if override.port is not None:
            result.port = override.port
        
        # Merge server-y stuff
        if override.autoInit is not None:
            result.autoInit = override.autoInit
        if override.bandwidthAlg is not None:
            result.bandwidthAlg = override.bandwidthAlg
        if override.filePatching is not None:
            result.filePatching = override.filePatching
        if override.limitFPS is not None:
            result.limitFPS = override.limitFPS
        if override.enableHT is not None:
            result.enableHT = override.enableHT
        if override.useOCAP is not None:
            result.useOCAP = override.useOCAP
        if override.numHeadless is not None:
            result.numHeadless = override.numHeadless
        
        # Merge collections
        if override.admins is not None:
            result.admins = override.admins
        if override.params is not None:
            result.params = override.params
        if override.world is not None:
            result.world = override.world
        if override.difficulty is not None:
            result.difficulty = override.difficulty
        if override.missions is not None:
            result.missions = override.missions
        
        # Merge mods (komplexer)
        if override.mods is not None:
            result.mods = self.merge_mods(result.mods or FileConfig_Mods(), override.mods)
        
        # Merge DLCs
        if override.dlcs is not None:
            result.dlcs = self.merge_dlcs(result.dlcs or FileConfig_Dlcs(), override.dlcs)
        
        # Merge custom mods
        if override.customMods is not None:
            result.customMods = self.merge_custom_mods(
                result.customMods or FileConfig_CustomMods(),
                override.customMods
            )
        
        return result
    
    def merge_mods(self, default_mods: FileConfig_Mods, override_mods: FileConfig_Mods) -> FileConfig_Mods:
        """
        Mergt Mod-Listen.
        
        Strategie:
        - Override is None → behalte Defaults
        - Override alle Kategorien leer [] → behalte Defaults (keine Overrides)
        - Override hat non-empty Categories → ersetze nur diese
        - Override minus_mods [-] → entferne diese Mods zusätzlich
        """
        result = deepcopy(default_mods)
        
        # Wenn override_mods None ist oder gar nicht gesetzt, gib Defaults zurück
        if override_mods is None:
            return result
        
        # Prüfe ob override_mods ALLE Kategorien leer hat (= keine echten Overrides)
        categories = [
            "serverMods", "baseMods", "clientMods", "maps", "missionMods",
            "extraServer", "extraBase", "extraClient", "extraMaps", "extraMission",
            "minus_mods"
        ]
        
        # Finde kategor mit non-empty Override
        has_any_override = False
        for cat in categories:
            override_list = getattr(override_mods, cat, None)
            if override_list and len(override_list) > 0:
                has_any_override = True
                break
        
        # Wenn KEINE non-empty Override gefunden, dann sind alle Override [] = "no override"
        if not has_any_override:
            return result
        
        # Ansonsten: mergen der Override-Mods
        for cat in categories:
            default_list = getattr(default_mods, cat, None) or []
            override_list = getattr(override_mods, cat, None)
            
            if override_list is None:
                # Nicht gesetzt → behalte Default
                merged = default_list
            elif len(override_list) > 0:
                # Override hat Content → ersetze
                merged = override_list
            else:
                # Override ist [] (leer) → behalte Default (nicht leer!)
                merged = default_list
            
            setattr(result, cat, merged)
        
        return result
    
    def merge_dlcs(self, default_dlcs: FileConfig_Dlcs, override_dlcs: FileConfig_Dlcs) -> FileConfig_Dlcs:
        """Mergt DLC-Flags."""
        result = deepcopy(default_dlcs)
        
        dlc_fields = [
            "contact", "csla_iron_curtain", "global_mobilization",
            "sog_prairie_fire", "western_sahara", "spearhead_1944",
            "reaction_forces", "expeditionary_forces"
        ]
        
        for field in dlc_fields:
            override_val = getattr(override_dlcs, field, None)
            if override_val is not None:
                setattr(result, field, override_val)
        
        return result
    
    def merge_custom_mods(self, default_custom: FileConfig_CustomMods, override_custom: FileConfig_CustomMods) -> FileConfig_CustomMods:
        """Mergt Custom Mods."""
        result = FileConfig_CustomMods()
        
        result.mods = override_custom.mods if override_custom.mods is not None else default_custom.mods
        result.serverMods = override_custom.serverMods if override_custom.serverMods is not None else default_custom.serverMods
        
        return result
    
    def compute_delta(self, defaults: FileConfig_Defaults, merged: FileConfig_Defaults) -> Dict[str, Any]:
        """
        Berechnet Unterschiede zwischen Defaults und Merged für Anzeige im Frontend.
        
        Zeigt dem Benutzer: "Diese Einstellungen unterscheiden sich von Defaults"
        
        Returns:
            Dict mit paths → (default_val, merged_val)
        """
        deltas = {}
        
        # Scalar fields
        scalars = [
            "maxPlayers", "hostname", "serverPassword", "adminPassword",
            "port", "autoInit", "bandwidthAlg", "filePatching", "limitFPS",
            "enableHT", "useOCAP", "numHeadless", "world", "difficulty"
        ]
        
        for field in scalars:
            default_val = getattr(defaults, field, None)
            merged_val = getattr(merged, field, None)
            if default_val != merged_val:
                deltas[f"/{field}"] = {"default": default_val, "merged": merged_val}
        
        # Mods
        if defaults.mods != merged.mods:
            deltas["/mods"] = self._delta_mods(defaults.mods, merged.mods)
        
        # DLCs
        if defaults.dlcs != merged.dlcs:
            deltas["/dlcs"] = self._delta_dlcs(defaults.dlcs, merged.dlcs)
        
        return deltas
    
    def _delta_mods(self, default_mods: Optional[FileConfig_Mods], merged_mods: Optional[FileConfig_Mods]) -> Dict:
        """Berechnet Mod-Unterschiede."""
        delta = {}
        
        if not default_mods or not merged_mods:
            return delta
        
        categories = [
            "serverMods", "baseMods", "clientMods", "maps", "missionMods",
            "extraServer", "extraBase", "extraClient", "extraMaps", "extraMission", "minus_mods"
        ]
        
        for cat in categories:
            default_list = getattr(default_mods, cat, []) or []
            merged_list = getattr(merged_mods, cat, []) or []
            
            if default_list != merged_list:
                default_ids = {m.id for m in default_list}
                merged_ids = {m.id for m in merged_list}
                
                added_ids = merged_ids - default_ids
                removed_ids = default_ids - merged_ids
                
                delta[cat] = {
                    "added": [int(mid) for mid in added_ids],
                    "removed": [int(mid) for mid in removed_ids],
                    "count": len(merged_list)
                }
        
        return delta
    
    def _delta_dlcs(self, default_dlcs: Optional[FileConfig_Dlcs], merged_dlcs: Optional[FileConfig_Dlcs]) -> Dict:
        """Berechnet DLC-Unterschiede."""
        delta = {}
        
        if not default_dlcs or not merged_dlcs:
            return delta
        
        dlc_fields = [
            "contact", "csla_iron_curtain", "global_mobilization",
            "sog_prairie_fire", "western_sahara", "spearhead_1944",
            "reaction_forces", "expeditionary_forces"
        ]
        
        for field in dlc_fields:
            default_val = getattr(default_dlcs, field, False)
            merged_val = getattr(merged_dlcs, field, False)
            if default_val != merged_val:
                delta[field] = {"default": default_val, "merged": merged_val}
        
        return delta

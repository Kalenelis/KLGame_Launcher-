# core/profile_manager.py
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FileRule:
    """One config swap rule: copy src -> dst before launch."""
    src: str
    dst: str
    enabled: bool = True


@dataclass
class DisplayProfile:
    """Display / launch profile (PC/TV/MonitorX) with config swap rules."""
    key: str                       # e.g. "monitor_1"
    name: str                      # display name shown in UI
    monitor_id: str                # "0","1","2" (matches monitors.json keys)
    move_window: bool = True
    force_focus: bool = True
    window_mode: str = "borderless"  # "borderless" | "fullscreen" | "windowed"
    rules: List[FileRule] = field(default_factory=list)


def compute_game_id(game: Dict[str, Any]) -> str:
    """
    Stable id for last profile. If game already has 'id', keep it.
    Otherwise compute from exe_path + name (stable enough).
    """
    gid = (game or {}).get("id")
    if isinstance(gid, str) and gid.strip():
        return gid.strip()
    name = str((game or {}).get("name", "")).strip()
    exe = str((game or {}).get("exe_path", "")).strip().lower()
    h = hashlib.md5(f"{name}|{exe}".encode("utf-8"), usedforsecurity=False).hexdigest()
    return h[:12]


class LastProfileStore:
    """Persists last selected profile per game."""
    def __init__(self, path: str) -> None:
        self.path = path
        self._map: Dict[str, str] = {}
        self.load()

    def load(self) -> None:
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._map = {str(k): str(v) for k, v in data.items()}
        except Exception:
            self._map = {}

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._map, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get(self, game_id: str) -> Optional[str]:
        v = self._map.get(str(game_id))
        return str(v) if v is not None else None

    def set(self, game_id: str, monitor_id: str) -> None:
        self._map[str(game_id)] = str(monitor_id)
        self.save()


def game_to_profiles(game: Dict[str, Any], monitors: Dict[str, str]) -> List[DisplayProfile]:
    """
    Convert your existing schema:
      game["monitor_profiles"][profile_key] = {"monitor_id":"1", "configs":[...], ...}
    into DisplayProfile objects. This keeps backward compatibility.
    """
    out: List[DisplayProfile] = []
    mp = (game or {}).get("monitor_profiles") or {}
    if not isinstance(mp, dict):
        return out

    for key, prof in mp.items():
        if not isinstance(prof, dict):
            continue
        mon_id = str(prof.get("monitor_id", "")).strip()
        display_name = monitors.get(mon_id) or key
        rules: List[FileRule] = []
        cfgs = prof.get("configs", [])
        if isinstance(cfgs, list):
            for c in cfgs:
                if not isinstance(c, dict):
                    continue
                src = str(c.get("src", "")).strip()
                dst = str(c.get("dst", "")).strip()
                if src and dst:
                    rules.append(FileRule(src=src, dst=dst, enabled=bool(c.get("enabled", True))))
        out.append(
            DisplayProfile(
                key=str(key),
                name=str(display_name),
                monitor_id=mon_id,
                move_window=bool(prof.get("move_window", True)),
                force_focus=bool(prof.get("force_focus", True)),
                window_mode=str(prof.get("window_mode", "borderless")),
                rules=rules,
            )
        )
    return out


def profiles_to_game(game: Dict[str, Any], profiles: List[DisplayProfile]) -> Dict[str, Any]:
    """Write DisplayProfile objects back into your existing games.json schema."""
    mp: Dict[str, Any] = {}
    for p in profiles:
        mp[p.key] = {
            "monitor_id": str(p.monitor_id),
            "fps_limit": int((game.get("monitor_profiles", {}) or {}).get(p.key, {}).get("fps_limit", 0) or 0),
            "fps_method": str((game.get("monitor_profiles", {}) or {}).get(p.key, {}).get("fps_method", "auto") or "auto"),
            "move_window": bool(p.move_window),
            "force_focus": bool(p.force_focus),
            "window_mode": str(p.window_mode),
            "configs": [
                {"src": r.src, "dst": r.dst, "enabled": r.enabled}
                for r in (p.rules or [])
                if r.src and r.dst
            ],
        }
    game["monitor_profiles"] = mp
    if "id" not in game:
        game["id"] = compute_game_id(game)
    return game

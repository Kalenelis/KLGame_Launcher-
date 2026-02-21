# core/launch_pipeline.py
from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, Optional, Tuple

from .config_swapper import ConfigSwapper, SwapSession
from .profile_manager import DisplayProfile
from .display_manager_win import wait_for_main_window, move_window_to_monitor, force_foreground, WIN32_AVAILABLE


class LaunchPipeline:
    """
    Apply profile configs -> start game -> move/focus window -> restore configs.

    UI calls launch_with_session(), then waits for proc (async or blocking),
    and must call restore(session) in finally.
    """
    def __init__(self, backups_root: str) -> None:
        self.swapper = ConfigSwapper(backups_root)

    def launch_with_session(self, game: Dict[str, Any], profile: DisplayProfile) -> Tuple[subprocess.Popen, SwapSession]:
        exe = str(game.get("exe_path", "")).strip()
        if not exe:
            raise RuntimeError("Game exe_path is empty")

        session = self.swapper.apply(profile.rules)

        try:
            proc = subprocess.Popen([exe], cwd=os.path.dirname(exe) or None)

            if WIN32_AVAILABLE and profile.move_window:
                hwnd = wait_for_main_window(proc.pid, timeout_s=12.0)
                if hwnd:
                    try:
                        mon_index = int(profile.monitor_id)
                    except Exception:
                        mon_index = 0
                    borderless = (profile.window_mode or "").lower() in ("borderless", "fullscreen")
                    move_window_to_monitor(hwnd, mon_index, borderless=borderless)
                    if profile.force_focus:
                        force_foreground(hwnd)

            return proc, session
        except Exception:
            self.swapper.restore(session)
            raise

    def restore(self, session: SwapSession) -> None:
        self.swapper.restore(session)

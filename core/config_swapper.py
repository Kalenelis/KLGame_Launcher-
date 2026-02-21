# core/config_swapper.py
from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from typing import List, Optional

from .profile_manager import FileRule


@dataclass
class BackupEntry:
    dst: str
    existed: bool
    backup_path: Optional[str]


@dataclass
class SwapSession:
    session_id: str
    backups: List[BackupEntry]


def _safe_mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


class ConfigSwapper:
    """
    Applies a list of FileRule (src -> dst). Creates backups so restore is safe.
    """
    def __init__(self, backups_root: str) -> None:
        self.backups_root = backups_root

    def apply(self, rules: List[FileRule]) -> SwapSession:
        sid = str(int(time.time() * 1000))
        session_dir = os.path.join(self.backups_root, sid)
        _safe_mkdir(session_dir)

        backups: List[BackupEntry] = []

        for idx, r in enumerate(rules or []):
            if not r.enabled:
                continue
            src = os.path.abspath(r.src)
            dst = os.path.abspath(r.dst)

            if not src or not dst or not os.path.exists(src):
                # skip invalid rule
                continue

            dst_dir = os.path.dirname(dst)
            if dst_dir:
                _safe_mkdir(dst_dir)

            existed = os.path.exists(dst)
            backup_path = None

            if existed:
                backup_path = os.path.join(session_dir, f"{idx}__" + os.path.basename(dst))
                try:
                    shutil.copy2(dst, backup_path)
                except Exception:
                    backup_path = None

            # apply (overwrite)
            try:
                shutil.copy2(src, dst)
            except Exception:
                # if apply failed, try to revert what we can for this file
                if existed and backup_path and os.path.exists(backup_path):
                    try:
                        shutil.copy2(backup_path, dst)
                    except Exception:
                        pass

            backups.append(BackupEntry(dst=dst, existed=existed, backup_path=backup_path))

        return SwapSession(session_id=sid, backups=backups)

    def restore(self, session: SwapSession) -> None:
        if not session:
            return
        session_dir = os.path.join(self.backups_root, session.session_id)

        for b in session.backups or []:
            try:
                if b.existed:
                    if b.backup_path and os.path.exists(b.backup_path):
                        shutil.copy2(b.backup_path, b.dst)
                else:
                    # file didn't exist before -> remove it if we created it
                    if os.path.exists(b.dst):
                        os.remove(b.dst)
            except Exception:
                pass

        # cleanup backups
        try:
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir, ignore_errors=True)
        except Exception:
            pass

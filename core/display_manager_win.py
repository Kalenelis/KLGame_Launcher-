# core/display_manager_win.py
from __future__ import annotations

import time
from typing import Optional, Tuple

try:
    import win32gui
    import win32con
    import win32process
    import win32api
    WIN32_AVAILABLE = True
except Exception:
    WIN32_AVAILABLE = False


def _enum_windows_for_pid(pid: int) -> list[int]:
    hwnds: list[int] = []
    if not WIN32_AVAILABLE:
        return hwnds

    def cb(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            _, wp = win32process.GetWindowThreadProcessId(hwnd)
            if wp == pid:
                # skip tool windows
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                if style & win32con.WS_EX_TOOLWINDOW:
                    return True
                hwnds.append(hwnd)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(cb, None)
    except Exception:
        pass
    return hwnds


def wait_for_main_window(pid: int, timeout_s: float = 12.0) -> Optional[int]:
    if not WIN32_AVAILABLE:
        return None
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        hwnds = _enum_windows_for_pid(pid)
        if hwnds:
            # heuristic: pick first; could be improved by checking window title
            return hwnds[0]
        time.sleep(0.12)
    return None


def get_monitor_rect_by_index(monitor_index: int) -> Optional[Tuple[int, int, int, int]]:
    """Returns (left, top, right, bottom) for monitor index."""
    if not WIN32_AVAILABLE:
        return None

    monitors: list[Tuple[int,int,int,int]] = []

    def cb(hMon, hdc, lprc, data):
        try:
            mi = win32api.GetMonitorInfo(hMon)
            r = mi.get("Monitor")
            if r:
                monitors.append((r[0], r[1], r[2], r[3]))
        except Exception:
            pass
        return True

    try:
        win32api.EnumDisplayMonitors(None, None, cb, None)
    except Exception:
        return None

    if 0 <= monitor_index < len(monitors):
        return monitors[monitor_index]
    return None


def move_window_to_monitor(hwnd: int, monitor_index: int, borderless: bool = True) -> None:
    if not WIN32_AVAILABLE:
        return
    rect = get_monitor_rect_by_index(monitor_index)
    if not rect:
        return
    l, t, r, b = rect
    w = r - l
    h = b - t

    try:
        # ensure visible
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        # resize/move
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, l, t, w, h,
                              win32con.SWP_SHOWWINDOW)
        if borderless:
            # Make it borderless-ish by clearing style bits (best effort)
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            style &= ~(win32con.WS_CAPTION | win32con.WS_THICKFRAME)
            win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
            win32gui.SetWindowPos(hwnd, None, l, t, w, h,
                                  win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW)
    except Exception:
        pass


def force_foreground(hwnd: int) -> None:
    if not WIN32_AVAILABLE:
        return
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass

import ctypes
from ctypes import wintypes
from PyQt6.QtGui import QGuiApplication

try:
    import win32gui
    import win32process
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

def get_physical_monitors_rects():
    if not WIN32_AVAILABLE:
        return []
    from ctypes import windll, byref, c_int

    class RECT(ctypes.Structure):
        _fields_ = [("left", c_int), ("top", c_int), ("right", c_int), ("bottom", c_int)]

    monitors = []

    def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        rect = ctypes.cast(lprcMonitor, ctypes.POINTER(RECT)).contents
        monitors.append((rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top))
        return True

    MonitorEnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC,
                                         ctypes.POINTER(RECT), wintypes.LPARAM)
    enum_proc = MonitorEnumProc(callback)
    if not windll.user32.EnumDisplayMonitors(None, None, enum_proc, 0):
        return []
    return monitors

def get_monitors_info():
    monitors = []
    screens = QGuiApplication.screens()
    phys_rects = get_physical_monitors_rects() if WIN32_AVAILABLE else []
    for i, screen in enumerate(screens):
        name = screen.name() or f"Monitor {i+1}"
        manufacturer = screen.manufacturer() or ""
        model = screen.model() or ""
        qt_geometry = screen.geometry()
        refresh = screen.refreshRate()
        if i < len(phys_rects):
            x, y, width, height = phys_rects[i]
        else:
            width = screen.size().width()
            height = screen.size().height()
            x = qt_geometry.x()
            y = qt_geometry.y()
        if manufacturer and model:
            display_name = f"{manufacturer} {model} ({width}x{height})"
        else:
            display_name = f"{name} ({width}x{height})"
        monitors.append({
            "id": i,
            "name": name,
            "manufacturer": manufacturer,
            "model": model,
            "width": width,
            "height": height,
            "geometry": qt_geometry,
            "refresh_rate": refresh,
            "display_name": display_name
        })
    return monitors
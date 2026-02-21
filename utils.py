import os
import json
import hashlib
import tempfile
import shutil
from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "games.json")
ICONS_DIR = os.path.join(SCRIPT_DIR, "game_icons")
BUTTON_ICONS_DIR = os.path.join(SCRIPT_DIR, "buttons_icons")
MONITORS_FILE = os.path.join(SCRIPT_DIR, "monitors.json")

if not os.path.exists(ICONS_DIR):
    os.makedirs(ICONS_DIR)

try:
    import win32ui
    import win32gui
    import win32con
    import win32api
    import win32process
    WIN32_AVAILABLE = True
    if hasattr(win32api, 'ExtractIconEx'):
        ExtractIconEx = win32api.ExtractIconEx
    elif hasattr(win32gui, 'ExtractIconEx'):
        ExtractIconEx = win32gui.ExtractIconEx
    else:
        ExtractIconEx = None
except ImportError:
    WIN32_AVAILABLE = False
    ExtractIconEx = None

def load_button_icon(filename, size=(24, 24)):
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtCore import Qt
    path = os.path.join(BUTTON_ICONS_DIR, filename)
    if os.path.exists(path):
        pixmap = QPixmap(path)
        return pixmap.scaled(size[0], size[1],
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    return None

def extract_icon_from_exe(exe_path, output_path, size=(128, 128)):
    if not WIN32_AVAILABLE or ExtractIconEx is None:
        return create_placeholder_icon(output_path, size, exe_path)
    try:
        large_icons, small_icons = ExtractIconEx(exe_path, 0)
        if large_icons and large_icons[0]:
            hicon = large_icons[0]
            info = win32gui.GetIconInfo(hicon)
            if info and info[4]:
                hbitmap = info[4]
                temp_bmp = os.path.join(tempfile.gettempdir(),
                                        f"temp_icon_{hashlib.md5(exe_path.encode()).hexdigest()}.bmp")
                bitmap = win32ui.CreateBitmapFromHandle(hbitmap)
                dc = win32ui.CreateDC()
                mem_dc = dc.CreateCompatibleDC()
                mem_dc.SelectObject(bitmap)
                bitmap.SaveBitmapFile(mem_dc, temp_bmp)
                try:
                    mem_dc.DeleteDC()
                except:
                    pass
                try:
                    dc.DeleteDC()
                except:
                    pass
                if os.path.exists(temp_bmp):
                    img = Image.open(temp_bmp)
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    img = img.resize(size, Image.Resampling.LANCZOS)
                    img.save(output_path, "PNG")
                    os.remove(temp_bmp)
                    return output_path
    except Exception:
        pass
    finally:
        for icons in (large_icons, small_icons):
            if icons:
                for icon in icons:
                    if icon:
                        try:
                            win32gui.DestroyIcon(icon)
                        except:
                            pass
    return create_placeholder_icon(output_path, size, exe_path)

def create_placeholder_icon(output_path, size, exe_path):
    img = Image.new('RGBA', size, (40, 40, 40, 255))
    draw = ImageDraw.Draw(img)
    for i in range(size[0]):
        for j in range(size[1]):
            x = i - size[0] / 2
            y = j - size[1] / 2
            dist = (x*x + y*y)**0.5
            if dist < size[0]/2:
                color = (
                    int(100 + 100 * (dist / (size[0]/2))),
                    int(80 + 80 * (dist / (size[0]/2))),
                    int(180 + 75 * (dist / (size[0]/2)))
                )
                draw.point((i, j), fill=color)
    game_name = os.path.basename(exe_path).replace('.exe', '').replace('.EXE', '')
    if game_name:
        try:
            font_size = size[0] // 2
            font = None
            font_paths = ["arial.ttf", "segoeui.ttf", "C:\\Windows\\Fonts\\Arial.ttf",
                          "C:\\Windows\\Fonts\\SegoeUI.ttf", "C:\\Windows\\Fonts\\Tahoma.ttf"]
            for path in font_paths:
                try:
                    font = ImageFont.truetype(path, font_size)
                    break
                except:
                    continue
            if font is None:
                font = ImageFont.load_default()
            try:
                bbox = draw.textbbox((0,0), game_name[0].upper(), font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            except AttributeError:
                text_width, text_height = draw.textsize(game_name[0].upper(), font=font)
            x = (size[0] - text_width) // 2
            y = (size[1] - text_height) // 2
            draw.text((x, y), game_name[0].upper(), fill='white', font=font)
        except:
            draw.ellipse([size[0]//2-10, size[1]//2-10, size[0]//2+10, size[1]//2+10], fill='white')
    img.save(output_path, "PNG")
    return output_path

def load_games():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        games = json.load(f)

    # Гарантируем, что monitor_profiles - словарь
    for game in games.values():
        if "monitor_profiles" not in game or not isinstance(game["monitor_profiles"], dict):
            game["monitor_profiles"] = {}

    global_monitors = load_monitors()
    changed = False

    for game in games.values():
        monitor_profiles = game.get("monitor_profiles", {})
        for mon_key, profile in list(monitor_profiles.items()):
            if "monitor_id" not in profile:
                try:
                    mon_id = int(mon_key.split('_')[-1])
                    profile["monitor_id"] = str(mon_id)
                except:
                    profile["monitor_id"] = "0"
            if "custom_name" in profile and profile["custom_name"]:
                mon_id = profile["monitor_id"]
                if mon_id not in global_monitors:
                    global_monitors[mon_id] = profile["custom_name"]
                    changed = True
                del profile["custom_name"]
        if "poster_path" not in game:
            game["poster_path"] = ""
        if "play_time" not in game:
            game["play_time"] = "0h"

    if changed:
        save_monitors(global_monitors)
        save_games(games)
    return games

def save_games(games):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(games, f, ensure_ascii=False, indent=4)

def load_monitors():
    if not os.path.exists(MONITORS_FILE):
        return {}
    try:
        with open(MONITORS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, IOError):
        return {}

def save_monitors(monitors):
    with open(MONITORS_FILE, "w", encoding="utf-8") as f:
        json.dump(monitors, f, ensure_ascii=False, indent=4)
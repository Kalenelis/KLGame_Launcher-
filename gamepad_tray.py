#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Универсальный менеджер геймпада с иконкой в трее.
Использует прямой вызов XInput через ctypes.
"""

import sys
import os
import json
import time
import subprocess
import threading
import locale
import ctypes
from ctypes import wintypes
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QDialog, QLineEdit, QComboBox, QSpinBox, QTextEdit,
    QSystemTrayIcon, QMenu, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread
from PyQt6.QtGui import QIcon, QAction

import psutil
import win32gui
import win32con
import win32api

# ---------- Прямая работа с XInput через ctypes ----------
# Определяем структуры XInput
class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ('wButtons', wintypes.WORD),
        ('bLeftTrigger', wintypes.BYTE),
        ('bRightTrigger', wintypes.BYTE),
        ('sThumbLX', wintypes.SHORT),
        ('sThumbLY', wintypes.SHORT),
        ('sThumbRX', wintypes.SHORT),
        ('sThumbRY', wintypes.SHORT)
    ]

class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ('dwPacketNumber', wintypes.DWORD),
        ('Gamepad', XINPUT_GAMEPAD)
    ]

# Пытаемся загрузить XInput библиотеку
XINPUT_AVAILABLE = False
xinput_dll = None
for dll in ['xinput1_4.dll', 'xinput1_3.dll', 'xinput9_1_0.dll']:
    try:
        xinput_dll = ctypes.windll.LoadLibrary(dll)
        XINPUT_AVAILABLE = True
        break
    except:
        continue

if xinput_dll:
    XInputGetState = xinput_dll.XInputGetState
    XInputGetState.argtypes = [wintypes.DWORD, ctypes.POINTER(XINPUT_STATE)]
    XInputGetState.restype = wintypes.DWORD

    # Константы ошибок
    ERROR_SUCCESS = 0
    ERROR_DEVICE_NOT_CONNECTED = 1167

# ---------- Конфигурация ----------
CONFIG_PATH = Path(__file__).parent / "gamepad_config.json"
ICON_PATH = Path(__file__).parent / "buttons_icons" / "gamepad.png"
LOCALES_DIR = Path(__file__).parent / "locales"

# ---------- Настройка переводов ----------
def load_translations():
    try:
        system_lang = locale.getdefaultlocale()[0][:2]
    except:
        system_lang = "en"

    translations = {}
    lang_file = LOCALES_DIR / f"gamepad_{system_lang}.json"
    if lang_file.exists():
        with open(lang_file, 'r', encoding='utf-8') as f:
            translations = json.load(f)
    else:
        fallback = LOCALES_DIR / "gamepad_en.json"
        if fallback.exists():
            with open(fallback, 'r', encoding='utf-8') as f:
                translations = json.load(f)
    return translations

translations = load_translations()

def tr(key, *args):
    text = translations.get(key, key)
    if args:
        return text.format(*args)
    return text

# ---------- Конфигурация ----------
def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    default = {
        "launcher_path": str(Path(__file__).parent / "GL.py"),
        "window_title": "Game Launcher",
        "controller_index": 0,
        "actions": [
            {
                "name": "Launch on main monitor",
                "combo": [7, 0],  # START + A
                "action": "launch_on_monitor",
                "monitor_index": 0
            },
            {
                "name": "Launch on TV",
                "combo": [7, 1],  # START + B
                "action": "launch_on_monitor",
                "monitor_index": 1
            },
            {
                "name": "Move to next monitor",
                "combo": [7, 2],  # START + X
                "action": "move_to_next_monitor"
            },
            {
                "name": "Minimize",
                "combo": [7, 3],  # START + Y
                "action": "minimize"
            },
            {
                "name": "Close",
                "combo": [7, 6],  # START + BACK
                "action": "close"
            }
        ]
    }
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(default, f, indent=4, ensure_ascii=False)
    return default

# ---------- Функции для работы с окнами и мониторами (Win32 API) ----------
def get_monitors():
    """Возвращает список кортежей (left, top, right, bottom) для всех мониторов."""
    monitors = []
    hdc = win32gui.GetDC(0)
    try:
        for hMonitor in win32api.EnumDisplayMonitors(hdc):
            monitor_info = win32api.GetMonitorInfo(hMonitor[0])
            # Используем Monitor, а не WorkArea (Monitor даёт полный экран, WorkArea - без панели задач)
            monitors.append(monitor_info['Monitor'])
    finally:
        win32gui.ReleaseDC(0, hdc)
    return monitors

def find_launcher_window(window_title):
    """Находит окно лаунчера по заголовку, используя Win32 API."""
    return win32gui.FindWindow(None, window_title)

def get_window_geometry(hwnd):
    """Возвращает геометрию окна по его HWND."""
    rect = win32gui.GetWindowRect(hwnd)
    return (rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])  # x, y, width, height

# ---------- Поток слушателя геймпада (XInput через ctypes) ----------
class GamepadListenerThread(QThread):
    actionTriggered = pyqtSignal(str)
    statusMessage = pyqtSignal(str)

    def __init__(self, config_provider):
        super().__init__()
        self.config_provider = config_provider
        self.running = True
        self.pressed = set()
        self.controller_index = 0
        self.gamepad_available = False
        self.check_gamepad()

    def check_gamepad(self):
        if not XINPUT_AVAILABLE:
            self.statusMessage.emit("XInput не доступен. Убедитесь, что у вас Windows 7+ и установлены драйверы.")
            return

        for i in range(4):
            state = XINPUT_STATE()
            result = XInputGetState(i, ctypes.byref(state))
            if result == ERROR_SUCCESS:
                self.controller_index = i
                self.gamepad_available = True
                self.statusMessage.emit(f"Геймпад подключён (контроллер {i})")
                return
            elif result != ERROR_DEVICE_NOT_CONNECTED:
                self.statusMessage.emit(f"Ошибка при проверке контроллера {i}: код {result}")

        self.statusMessage.emit("Геймпад не найден. Подключите Xbox-совместимый контроллер и запустите заново.")

    def run(self):
        if not XINPUT_AVAILABLE or not self.gamepad_available:
            self.statusMessage.emit("Слушатель геймпада остановлен - нет контроллера")
            return

        self.statusMessage.emit(f"Слушатель геймпада запущен (контроллер {self.controller_index})")

        # Маппинг кнопок для вашего геймпада (на основе предоставленных масок)
        button_map = [
            (0x1000, 0),  # A
            (0x2000, 1),  # B
            (0x4000, 2),  # X
            (0x8000, 3),  # Y
            (0x0100, 4),  # LB
            (0x0200, 5),  # RB
            (0x0020, 6),  # BACK
            (0x0010, 7),  # START
            (0x0040, 8),  # L3
            (0x0080, 9)   # R3
        ]

        last_buttons = 0

        while self.running:
            try:
                state = XINPUT_STATE()
                result = XInputGetState(self.controller_index, ctypes.byref(state))

                if result == ERROR_DEVICE_NOT_CONNECTED:
                    self.statusMessage.emit("Геймпад отключён")
                    self.gamepad_available = False
                    break
                elif result != ERROR_SUCCESS:
                    time.sleep(2)
                    continue

                buttons_mask = state.Gamepad.wButtons

                if buttons_mask == last_buttons:
                    time.sleep(0.05)
                    continue
                last_buttons = buttons_mask

                current_buttons = set()
                for mask, btn in button_map:
                    if buttons_mask & mask:
                        current_buttons.add(btn)

                new_pressed = current_buttons - self.pressed
                released = self.pressed - current_buttons

                for btn in new_pressed:
                    self.pressed.add(btn)
                    self.statusMessage.emit(f"Кнопка {btn} нажата")

                for btn in released:
                    self.pressed.discard(btn)

                config = self.config_provider()
                for act in config.get('actions', []):
                    combo = set(act.get('combo', []))
                    if combo and combo.issubset(self.pressed):
                        self.actionTriggered.emit(act['name'])
                        self.execute_action(act)
                        time.sleep(1)
                        break

                time.sleep(0.05)

            except Exception as e:
                self.statusMessage.emit(f"Ошибка в слушателе: {e}")
                time.sleep(2)

    def execute_action(self, action_cfg):
        act_type = action_cfg.get('action')
        if act_type == 'launch_on_monitor':
            monitor_idx = action_cfg.get('monitor_index', 0)
            self.launch_launcher(monitor_idx)
        elif act_type == 'move_to_next_monitor':
            self.move_to_next_monitor()
        elif act_type == 'minimize':
            self.minimize_window()
        elif act_type == 'close':
            self.close_window()

    def launch_launcher(self, monitor_idx):
        config = self.config_provider()
        launcher_path = config.get('launcher_path', '')
        window_title = config.get('window_title', 'Game Launcher')

        hwnd = find_launcher_window(window_title)

        if hwnd:
            self.statusMessage.emit("Лаунчер уже запущен, разворачиваю на весь монитор...")

            # Восстанавливаем, если свёрнуто
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.2)

            # Сначала максимизируем, чтобы окно заняло весь экран
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            time.sleep(0.2)

            monitors = get_monitors()
            if 0 <= monitor_idx < len(monitors):
                mon = monitors[monitor_idx]
                target_x, target_y = mon[0], mon[1]
                target_width = mon[2] - mon[0]
                target_height = mon[3] - mon[1]

                # Перемещаем на целевой монитор и задаём точный размер
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOP,
                    target_x, target_y,
                    target_width, target_height,
                    win32con.SWP_SHOWWINDOW
                )

                # Убеждаемся, что окно максимизировано
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)

                win32gui.SetForegroundWindow(hwnd)
                win32gui.BringWindowToTop(hwnd)

                self.statusMessage.emit(f"Окно развёрнуто на весь монитор {monitor_idx}")
            return

        # Лаунчер не запущен – запускаем и сразу разворачиваем
        if not os.path.exists(launcher_path):
            self.statusMessage.emit(f"Лаунчер не найден: {launcher_path}")
            return

        try:
            self.statusMessage.emit(f"Запускаю лаунчер из {launcher_path}")
            process = subprocess.Popen(
                [sys.executable, launcher_path],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
            )
            self.statusMessage.emit("Лаунчер запущен, ожидаем появления окна...")

            hwnd = None
            for _ in range(20):
                time.sleep(0.5)
                hwnd = find_launcher_window(window_title)
                if hwnd:
                    break

            if hwnd:
                # Максимизируем новое окно
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                time.sleep(0.2)

                monitors = get_monitors()
                if 0 <= monitor_idx < len(monitors):
                    mon = monitors[monitor_idx]
                    target_x, target_y = mon[0], mon[1]
                    target_width = mon[2] - mon[0]
                    target_height = mon[3] - mon[1]

                    win32gui.SetWindowPos(
                        hwnd,
                        win32con.HWND_TOP,
                        target_x, target_y,
                        target_width, target_height,
                        win32con.SWP_SHOWWINDOW
                    )

                    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                    win32gui.SetForegroundWindow(hwnd)
                    win32gui.BringWindowToTop(hwnd)

                    self.statusMessage.emit(f"Лаунчер запущен и развёрнут на весь монитор {monitor_idx}")
                else:
                    self.statusMessage.emit("Лаунчер запущен, но монитор не найден")
            else:
                self.statusMessage.emit("Лаунчер запущен, но окно не обнаружено")

        except Exception as e:
            self.statusMessage.emit(f"Не удалось запустить лаунчер: {e}")

    def move_to_next_monitor(self):
        config = self.config_provider()
        window_title = config.get('window_title', 'Game Launcher')

        hwnd = find_launcher_window(window_title)
        if not hwnd:
            self.statusMessage.emit("Окно лаунчера не найдено, запустите его сначала")
            return

        # Восстанавливаем, если свёрнуто
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.2)

        # Сначала максимизируем
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        time.sleep(0.2)

        rect = win32gui.GetWindowRect(hwnd)
        current_x, current_y = rect[0], rect[1]

        monitors = get_monitors()
        if not monitors:
            return

        cur_idx = 0
        for i, mon in enumerate(monitors):
            if mon[0] <= current_x < mon[2] and mon[1] <= current_y < mon[3]:
                cur_idx = i
                break

        next_idx = (cur_idx + 1) % len(monitors)
        target_mon = monitors[next_idx]

        # Перемещаем на следующий монитор и задаём точный размер
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOP,
            target_mon[0], target_mon[1],
            target_mon[2] - target_mon[0],
            target_mon[3] - target_mon[1],
            win32con.SWP_SHOWWINDOW
        )

        # Убеждаемся, что окно максимизировано
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)

        win32gui.SetForegroundWindow(hwnd)
        win32gui.BringWindowToTop(hwnd)

        self.statusMessage.emit(f"Окно развёрнуто на весь монитор {next_idx}")

    def minimize_window(self):
        config = self.config_provider()
        window_title = config.get('window_title', 'Game Launcher')

        hwnd = find_launcher_window(window_title)
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            self.statusMessage.emit("Окно свёрнуто")
        else:
            self.statusMessage.emit("Окно лаунчера не найдено")

    def close_window(self):
        config = self.config_provider()
        window_title = config.get('window_title', 'Game Launcher')

        hwnd = find_launcher_window(window_title)
        if hwnd:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            self.statusMessage.emit("Окно закрыто")
        else:
            self.statusMessage.emit("Окно лаунчера не найдено")

    def stop(self):
        self.running = False


# ---------- Диалог тестирования геймпада (XInput через ctypes) ----------
class GamepadTestDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Тест геймпада (XInput)")
        self.setFixedSize(600, 500)
        self.setStyleSheet("background-color: #0e1115; color: white;")

        layout = QVBoxLayout(self)

        controller_group = QGroupBox("Контроллер")
        controller_layout = QHBoxLayout()
        controller_group.setLayout(controller_layout)

        self.controller_combo = QComboBox()
        self.controller_combo.addItems(["Контроллер 0", "Контроллер 1", "Контроллер 2", "Контроллер 3"])
        self.controller_combo.currentIndexChanged.connect(self.on_controller_changed)
        controller_layout.addWidget(QLabel("Выберите контроллер:"))
        controller_layout.addWidget(self.controller_combo)
        controller_layout.addStretch()
        layout.addWidget(controller_group)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("background-color: #1a1e24; border: 1px solid #272c34; font-family: monospace;")
        layout.addWidget(self.text_edit)

        self.status_label = QLabel("Нажимайте кнопки на геймпаде...")
        self.status_label.setStyleSheet("color: #00bfff;")
        layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border-radius: 4px;
                padding: 8px 20px;
            }
            QPushButton:hover { background-color: #5a5a5a; }
        """)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.running = True
        self.current_controller = 0
        self.last_buttons = 0
        self.listener_thread = threading.Thread(target=self.listen_gamepad)
        self.listener_thread.daemon = True
        self.listener_thread.start()

        self.check_controller(0)

    def on_controller_changed(self, index):
        self.current_controller = index
        self.check_controller(index)
        self.text_edit.append(f"Переключено на контроллер {index}")

    def check_controller(self, index):
        if not XINPUT_AVAILABLE:
            self.status_label.setText("XInput не доступен")
            return
        state = XINPUT_STATE()
        result = XInputGetState(index, ctypes.byref(state))
        if result == ERROR_SUCCESS:
            self.status_label.setText(f"Контроллер {index} подключён ✓")
        else:
            self.status_label.setText(f"Контроллер {index} не подключён (код {result})")

    def listen_gamepad(self):
        button_names = {
            0: "A", 1: "B", 2: "X", 3: "Y",
            4: "LB", 5: "RB", 6: "BACK", 7: "START",
            8: "L3", 9: "R3"
        }

        button_masks = [
            (0x1000, 0), (0x2000, 1), (0x4000, 2), (0x8000, 3),
            (0x0100, 4), (0x0200, 5), (0x0020, 6), (0x0010, 7),
            (0x0040, 8), (0x0080, 9)
        ]

        while self.running:
            if not XINPUT_AVAILABLE:
                time.sleep(2)
                continue

            state = XINPUT_STATE()
            result = XInputGetState(self.current_controller, ctypes.byref(state))

            if result == ERROR_DEVICE_NOT_CONNECTED:
                self.add_message(f"Контроллер {self.current_controller} не подключён")
                time.sleep(2)
                continue
            elif result != ERROR_SUCCESS:
                time.sleep(1)
                continue

            buttons_mask = state.Gamepad.wButtons

            if buttons_mask != self.last_buttons:
                changed = buttons_mask ^ self.last_buttons
                for mask, btn in button_masks:
                    if changed & mask:
                        name = button_names.get(btn, f"Btn{btn}")
                        if buttons_mask & mask:
                            self.add_message(f"Кнопка {name} ({btn}) нажата, маска: {mask:#06x}")
                        else:
                            self.add_message(f"Кнопка {name} ({btn}) отпущена")
                self.last_buttons = buttons_mask

            time.sleep(0.05)

    def add_message(self, msg):
        def update():
            self.text_edit.append(f"[{time.strftime('%H:%M:%S')}] {msg}")

        QTimer.singleShot(0, update)

    def closeEvent(self, event):
        self.running = False
        event.accept()


# ---------- Диалог записи комбинации (XInput через ctypes) ----------
class ComboRecorderDialog(QDialog):
    comboRecorded = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("record_combo_title"))
        self.setFixedSize(400, 250)
        self.setStyleSheet("background-color: #0e1115; color: white;")

        layout = QVBoxLayout(self)

        self.label = QLabel(tr("record_combo_instruction"))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("font-size: 12px; color: #cccccc;")
        layout.addWidget(self.label)

        self.pressed_label = QLabel("Нажато: нет")
        self.pressed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pressed_label.setStyleSheet("font-size: 14px; color: #00bfff; font-weight: bold;")
        layout.addWidget(self.pressed_label)

        self.status_label = QLabel("Слушаем...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #4caf50;")
        layout.addWidget(self.status_label)

        self.button_names = {
            0: "A", 1: "B", 2: "X", 3: "Y",
            4: "LB", 5: "RB", 6: "BACK", 7: "START",
            8: "L3", 9: "R3"
        }

        self.button_masks = [
            (0x1000, 0), (0x2000, 1), (0x4000, 2), (0x8000, 3),
            (0x0100, 4), (0x0200, 5), (0x0020, 6), (0x0010, 7),
            (0x0040, 8), (0x0080, 9)
        ]

        self.pressed = set()
        self.recording = True
        self.last_activity = time.time()
        self.controller_index = 0
        self.last_buttons = 0

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_timeout)
        self.timer.start(100)

        self.listener_thread = threading.Thread(target=self.listen_gamepad)
        self.listener_thread.daemon = True
        self.listener_thread.start()

    def listen_gamepad(self):
        if not XINPUT_AVAILABLE:
            return

        while self.recording:
            state = XINPUT_STATE()
            result = XInputGetState(self.controller_index, ctypes.byref(state))

            if result == ERROR_SUCCESS:
                buttons_mask = state.Gamepad.wButtons
                if buttons_mask != self.last_buttons:
                    self.last_buttons = buttons_mask
                    current_buttons = set()
                    for mask, btn in self.button_masks:
                        if buttons_mask & mask:
                            current_buttons.add(btn)
                    if current_buttons != self.pressed:
                        self.pressed = current_buttons
                        self.last_activity = time.time()
                        self.update_pressed_display()
            time.sleep(0.05)

    def update_pressed_display(self):
        names = [f"{self.button_names.get(b, str(b))}({b})" for b in sorted(self.pressed)]
        text = ", ".join(names) if names else "нет"

        def update():
            self.pressed_label.setText(f"Нажато: {text}")

        QTimer.singleShot(0, update)

    def check_timeout(self):
        if self.recording and self.pressed and time.time() - self.last_activity > 2:
            self.finish_recording()

    def finish_recording(self):
        self.recording = False
        self.timer.stop()
        self.comboRecorded.emit(sorted(list(self.pressed)))
        self.accept()


# ---------- Виджет для редактирования действия ----------
class ActionWidget(QWidget):
    def __init__(self, action_data, parent=None):
        super().__init__(parent)
        self.action_data = action_data
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.name_edit = QLineEdit(action_data.get('name', ''))
        self.name_edit.setPlaceholderText(tr("action_name_placeholder"))
        self.name_edit.setStyleSheet(
            "background-color: #15181e; color: white; border: 1px solid #272c34; border-radius: 4px; padding: 3px;")
        layout.addWidget(self.name_edit)

        combo = action_data.get('combo', [])
        button_names = {0: "A", 1: "B", 2: "X", 3: "Y", 4: "LB", 5: "RB", 6: "BACK", 7: "START", 8: "L3", 9: "R3"}
        combo_str = ', '.join([f"{button_names.get(b, str(b))}({b})" for b in combo]) if combo else tr("combo_not_set")
        self.combo_label = QLabel(combo_str)
        self.combo_label.setMinimumWidth(200)
        self.combo_label.setStyleSheet("color: #00bfff;")
        layout.addWidget(self.combo_label)

        self.record_btn = QPushButton(tr("record_button"))
        self.record_btn.setStyleSheet("background-color: #4a4a4a; color: white; border-radius: 4px; padding: 3px;")
        self.record_btn.clicked.connect(self.record_combo)
        layout.addWidget(self.record_btn)

        self.action_combo = QComboBox()
        self.action_combo.addItems(["launch_on_monitor", "move_to_next_monitor", "minimize", "close"])
        self.action_combo.setCurrentText(action_data.get('action', 'launch_on_monitor'))
        self.action_combo.setStyleSheet(
            "background-color: #15181e; color: white; border: 1px solid #272c34; border-radius: 4px; padding: 3px;")
        self.action_combo.currentTextChanged.connect(self.on_action_changed)
        layout.addWidget(self.action_combo)

        self.monitor_spin = QSpinBox()
        self.monitor_spin.setMinimum(0)
        self.monitor_spin.setMaximum(10)
        self.monitor_spin.setValue(action_data.get('monitor_index', 0))
        self.monitor_spin.setStyleSheet(
            "background-color: #15181e; color: white; border: 1px solid #272c34; border-radius: 4px; padding: 3px;")
        self.monitor_spin.setVisible(self.action_combo.currentText() == 'launch_on_monitor')
        layout.addWidget(self.monitor_spin)

        self.delete_btn = QPushButton("X")
        self.delete_btn.setFixedSize(25, 25)
        self.delete_btn.setStyleSheet("background-color: red; color: white; border-radius: 3px; border: none;")
        self.delete_btn.clicked.connect(self.delete_self)
        layout.addWidget(self.delete_btn)

    def record_combo(self):
        dialog = ComboRecorderDialog(self)
        dialog.comboRecorded.connect(self.on_combo_recorded)
        dialog.exec()

    def on_combo_recorded(self, combo):
        self.action_data['combo'] = combo
        button_names = {0: "A", 1: "B", 2: "X", 3: "Y", 4: "LB", 5: "RB", 6: "BACK", 7: "START", 8: "L3", 9: "R3"}
        self.combo_label.setText(', '.join([f"{button_names.get(b, str(b))}({b})" for b in combo]))

    def on_action_changed(self, text):
        self.monitor_spin.setVisible(text == 'launch_on_monitor')

    def get_data(self):
        data = {
            "name": self.name_edit.text(),
            "combo": self.action_data.get('combo', []),
            "action": self.action_combo.currentText(),
        }
        if data["action"] == "launch_on_monitor":
            data["monitor_index"] = self.monitor_spin.value()
        return data

    def delete_self(self):
        parent_list = self.parent().parent()
        if isinstance(parent_list, QListWidget):
            for i in range(parent_list.count()):
                item = parent_list.item(i)
                if parent_list.itemWidget(item) is self:
                    parent_list.takeItem(i)
                    break


# ---------- Главное окно конфигуратора ----------
class ConfigWindow(QMainWindow):
    configChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("window_title"))
        self.resize(900, 650)
        self.setStyleSheet("background-color: #0e1115; color: white;")

        self.config = load_config()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.status_label = QLabel("Готов")
        self.status_label.setStyleSheet("color: #00bfff; padding: 5px;")
        layout.addWidget(self.status_label)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget { background-color: #1a1e24; border: 1px solid #272c34; border-radius: 4px; }")
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton(tr("add_action_button"))
        self.add_btn.setStyleSheet("background-color: #2b5e8c; color: white; border-radius: 4px; padding: 5px 10px;")
        self.add_btn.clicked.connect(self.add_action)
        btn_layout.addWidget(self.add_btn)

        self.save_btn = QPushButton(tr("save_button"))
        self.save_btn.setStyleSheet("background-color: #4a4a4a; color: white; border-radius: 4px; padding: 5px 10px;")
        self.save_btn.clicked.connect(self.save_config)
        btn_layout.addWidget(self.save_btn)

        self.test_btn = QPushButton("Тест геймпада")
        self.test_btn.setStyleSheet("background-color: #4a4a4a; color: white; border-radius: 4px; padding: 5px 10px;")
        self.test_btn.clicked.connect(self.test_gamepad)
        btn_layout.addWidget(self.test_btn)

        self.help_btn = QPushButton(tr("help_button"))
        self.help_btn.setStyleSheet("background-color: #4a4a4a; color: white; border-radius: 4px; padding: 5px 10px;")
        self.help_btn.clicked.connect(self.show_help)
        btn_layout.addWidget(self.help_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.refresh_list()
        self.update_gamepad_status()

    def update_gamepad_status(self):
        if not XINPUT_AVAILABLE:
            self.status_label.setText("XInput не доступен. Возможно, у вас старая Windows или отсутствуют драйверы.")
            return
        for i in range(4):
            state = XINPUT_STATE()
            result = XInputGetState(i, ctypes.byref(state))
            if result == ERROR_SUCCESS:
                self.status_label.setText(f"Геймпад подключён (контроллер {i}) ✓")
                return
        self.status_label.setText("Геймпад не найден. Подключите Xbox-совместимый контроллер.")

    def refresh_list(self):
        self.list_widget.clear()
        for act in self.config.get('actions', []):
            self.add_action_widget(act)

    def add_action_widget(self, action_data):
        item = QListWidgetItem()
        widget = ActionWidget(action_data, self)
        item.setSizeHint(widget.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)

    def add_action(self):
        new = {
            "name": "Новое действие",
            "combo": [],
            "action": "launch_on_monitor",
            "monitor_index": 0
        }
        self.add_action_widget(new)

    def save_config(self):
        actions = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget:
                actions.append(widget.get_data())
        self.config['actions'] = actions
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            self.configChanged.emit()
            QMessageBox.information(self, tr("save_button"), tr("config_saved"))
        except Exception as e:
            QMessageBox.critical(self, tr("error"), tr("config_save_error", str(e)))

    def test_gamepad(self):
        if not XINPUT_AVAILABLE:
            QMessageBox.critical(self, "Ошибка", "XInput не доступен на этой системе")
            return
        dialog = GamepadTestDialog(self)
        dialog.exec()

    def show_help(self):
        msg = QMessageBox(self)
        msg.setWindowTitle(tr("help_title"))
        msg.setTextFormat(Qt.TextFormat.RichText)
        help_text = tr("help_text")
        xinput_help = """
        <p><b>Соответствие кнопок XInput:</b><br>
        0 = A<br>
        1 = B<br>
        2 = X<br>
        3 = Y<br>
        4 = LB<br>
        5 = RB<br>
        6 = BACK<br>
        7 = START<br>
        8 = L3 (нажатие левого стика)<br>
        9 = R3 (нажатие правого стика)
        </p>
        """
        msg.setText(help_text + xinput_help)
        msg.setStyleSheet("QLabel { color: white; }")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def closeEvent(self, event):
        event.ignore()
        self.hide()


# ---------- Главный класс приложения с треем ----------
class GamepadTrayApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)

        if ICON_PATH.exists():
            self.tray_icon = QIcon(str(ICON_PATH))
        else:
            self.tray_icon = QIcon()

        self.tray_menu = QMenu()

        show_action = QAction(tr("tray_show"), self)
        show_action.triggered.connect(self.show_window)
        self.tray_menu.addAction(show_action)

        hide_action = QAction(tr("tray_hide"), self)
        hide_action.triggered.connect(self.hide_window)
        self.tray_menu.addAction(hide_action)

        self.tray_menu.addSeparator()

        restart_action = QAction(tr("tray_restart"), self)
        restart_action.triggered.connect(self.restart_listener)
        self.tray_menu.addAction(restart_action)

        self.tray_menu.addSeparator()

        exit_action = QAction(tr("tray_exit"), self)
        exit_action.triggered.connect(self.exit_app)
        self.tray_menu.addAction(exit_action)

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.tray_icon)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.setToolTip(tr("tray_tooltip"))
        self.tray.show()

        self.config_window = ConfigWindow()
        self.config_window.configChanged.connect(self.restart_listener)

        self.listener_thread = GamepadListenerThread(self.get_current_config)
        self.listener_thread.actionTriggered.connect(self.on_action_triggered)
        self.listener_thread.statusMessage.connect(self.on_status_message)
        self.listener_thread.start()

    def get_current_config(self):
        return self.config_window.config

    def on_action_triggered(self, name):
        self.config_window.status_label.setText(f"Действие: {name}")

    def on_status_message(self, msg):
        self.config_window.status_label.setText(msg)

    def show_window(self):
        self.config_window.show()
        self.config_window.raise_()
        self.config_window.activateWindow()

    def hide_window(self):
        self.config_window.hide()

    def restart_listener(self):
        self.listener_thread.stop()
        self.listener_thread.wait(2000)
        self.listener_thread = GamepadListenerThread(self.get_current_config)
        self.listener_thread.actionTriggered.connect(self.on_action_triggered)
        self.listener_thread.statusMessage.connect(self.on_status_message)
        self.listener_thread.start()

    def exit_app(self):
        self.listener_thread.stop()
        self.listener_thread.wait(2000)
        self.quit()


def main():
    if not XINPUT_AVAILABLE:
        print("=" * 50)
        print("ПРЕДУПРЕЖДЕНИЕ: XInput не доступен!")
        print("Убедитесь, что у вас Windows 7/8/10/11 и установлены драйверы для геймпада.")
        print("Программа будет работать, но функции геймпада недоступны.")
        print("=" * 50)

    app = GamepadTrayApp(sys.argv)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
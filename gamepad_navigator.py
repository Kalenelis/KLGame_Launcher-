import time
import ctypes
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from xinput import XINPUT_AVAILABLE, XINPUT_STATE, XInputGetState, ERROR_SUCCESS

class GamepadNavigator(QThread):
    navigate = pyqtSignal(str, int)

    def __init__(self):
        super().__init__()
        self.running = True
        self.controller_index = 0
        self.gamepad_available = False
        self.last_button_time = 0
        self.button_cooldown = 0.3
        self.check_gamepad()

        self.repeat_timer = QTimer()
        self.repeat_timer.setInterval(150)
        self.repeat_timer.timeout.connect(self.repeat_navigation)
        self.current_direction = None

    def check_gamepad(self):
        if not XINPUT_AVAILABLE:
            return
        for i in range(4):
            state = XINPUT_STATE()
            result = XInputGetState(i, ctypes.byref(state))
            if result == ERROR_SUCCESS:
                self.controller_index = i
                self.gamepad_available = True
                return

    def run(self):
        while self.running:
            if not self.gamepad_available:
                time.sleep(1)
                self.check_gamepad()
                continue
            try:
                state = XINPUT_STATE()
                result = XInputGetState(self.controller_index, ctypes.byref(state))
                if result != ERROR_SUCCESS:
                    self.gamepad_available = False
                    time.sleep(1)
                    continue
                now = time.time()
                buttons = state.Gamepad.wButtons
                if buttons & 0x1000:  # A
                    if now - self.last_button_time > self.button_cooldown:
                        self.last_button_time = now
                        self.navigate.emit('activate', 0)
                if buttons & 0x0001:  # Up
                    if now - self.last_button_time > self.button_cooldown:
                        self.last_button_time = now
                        self.navigate.emit('up', 0)
                elif buttons & 0x0002:  # Down
                    if now - self.last_button_time > self.button_cooldown:
                        self.last_button_time = now
                        self.navigate.emit('down', 0)
                elif buttons & 0x0004:  # Left
                    if now - self.last_button_time > self.button_cooldown:
                        self.last_button_time = now
                        self.navigate.emit('left', 0)
                elif buttons & 0x0008:  # Right
                    if now - self.last_button_time > self.button_cooldown:
                        self.last_button_time = now
                        self.navigate.emit('right', 0)

                lx = state.Gamepad.sThumbLX
                ly = state.Gamepad.sThumbLY
                deadzone = 5000
                direction = None
                if abs(lx) > deadzone or abs(ly) > deadzone:
                    if abs(lx) > abs(ly):
                        direction = 'right' if lx > 0 else 'left'
                    else:
                        direction = 'down' if ly > 0 else 'up'

                if direction != self.current_direction:
                    self.current_direction = direction
                    if direction:
                        self.navigate.emit(direction, 0)
                        self.repeat_timer.start()
                    else:
                        self.repeat_timer.stop()
                time.sleep(0.05)
            except Exception:
                time.sleep(1)

    def repeat_navigation(self):
        if self.current_direction:
            self.navigate.emit(self.current_direction, 1)

    def stop(self):
        self.running = False
        self.repeat_timer.stop()
        self.wait(2000)
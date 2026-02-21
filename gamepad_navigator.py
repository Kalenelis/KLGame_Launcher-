import time
import ctypes
from PyQt6.QtCore import QThread, pyqtSignal
from xinput import XINPUT_AVAILABLE, XINPUT_STATE, XInputGetState, ERROR_SUCCESS

class GamepadNavigator(QThread):
    """
    Safe XInput polling thread.

    IMPORTANT:
    - No QTimer inside QThread (can crash Qt/Windows).
    - All repeats handled by time-based logic in this thread.
    - Emits: navigate(action: str, repeat: int)
        repeat = 0 for initial press, 1.. for repeated holds.
    """
    navigate = pyqtSignal(str, int)

    def __init__(self):
        super().__init__()
        self.running = True
        self.controller_index = 0
        self.gamepad_available = False

        # debounce / repeat
        self._last_packet = None
        self._last_buttons = 0
        self._last_emit_time = 0.0

        self.repeat_delay = 0.35
        self.repeat_interval = 0.12
        self._hold_action = None
        self._hold_started = 0.0
        self._next_repeat = 0.0
        self._repeat_count = 0

        self.button_cooldown = 0.08  # minimal gap between different actions

        self.check_gamepad()

    def stop(self):
        self.running = False

    def check_gamepad(self):
        self.gamepad_available = bool(XINPUT_AVAILABLE)

    def run(self):
        if not XINPUT_AVAILABLE:
            return

        state = XINPUT_STATE()
        while self.running:
            try:
                res = XInputGetState(self.controller_index, ctypes.byref(state))
                if res != ERROR_SUCCESS:
                    # controller not connected
                    self._hold_action = None
                    time.sleep(0.25)
                    continue

                pkt = int(state.dwPacketNumber)
                buttons = int(state.Gamepad.wButtons)

                now = time.time()

                # detect edge: any change
                changed = (buttons != self._last_buttons) or (self._last_packet != pkt)
                if changed:
                    # on release of held buttons, clear hold
                    if buttons == 0:
                        self._hold_action = None
                        self._repeat_count = 0

                    # map buttons to actions on press
                    action = self._map_buttons_to_action(buttons, self._last_buttons)
                    if action and (now - self._last_emit_time) >= self.button_cooldown:
                        self.navigate.emit(action, 0)
                        self._last_emit_time = now

                        # hold repeat for left/right only
                        if action in ("left", "right"):
                            self._hold_action = action
                            self._hold_started = now
                            self._next_repeat = now + self.repeat_delay
                            self._repeat_count = 0
                        else:
                            self._hold_action = None
                            self._repeat_count = 0

                    self._last_buttons = buttons
                    self._last_packet = pkt

                # repeat logic
                if self._hold_action and now >= self._next_repeat:
                    self._repeat_count += 1
                    self.navigate.emit(self._hold_action, self._repeat_count)
                    self._next_repeat = now + self.repeat_interval

                time.sleep(0.01)
            except Exception:
                # never crash the app due to input thread
                time.sleep(0.25)

    def _map_buttons_to_action(self, buttons: int, prev_buttons: int):
        """
        Return action string for NEW press events only.
        """
        newly_pressed = buttons & (~prev_buttons)

        # XInput button flags
        DPAD_UP    = 0x0001
        DPAD_DOWN  = 0x0002
        DPAD_LEFT  = 0x0004
        DPAD_RIGHT = 0x0008
        START      = 0x0010
        BACK       = 0x0020
        LB         = 0x0100
        RB         = 0x0200
        A          = 0x1000
        B          = 0x2000
        X          = 0x4000
        Y          = 0x8000

        if newly_pressed & DPAD_LEFT:
            return "left"
        if newly_pressed & DPAD_RIGHT:
            return "right"
        if newly_pressed & DPAD_UP:
            return "up"
        if newly_pressed & DPAD_DOWN:
            return "down"
        if newly_pressed & A:
            return "activate"
        if newly_pressed & B:
            return "back"
        if newly_pressed & Y:
            return "y"
        if newly_pressed & X:
            return "x"
        if newly_pressed & LB:
            return "lb"
        if newly_pressed & RB:
            return "rb"
        if newly_pressed & START:
            return "start"
        if newly_pressed & BACK:
            return "back"
        return None

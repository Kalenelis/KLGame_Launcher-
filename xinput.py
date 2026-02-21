import ctypes
from ctypes import wintypes

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
    ERROR_SUCCESS = 0
    ERROR_DEVICE_NOT_CONNECTED = 1167
else:
    XInputGetState = None
    ERROR_SUCCESS = 0
    ERROR_DEVICE_NOT_CONNECTED = 1167
"""
Wake Executor for Phase 6.

Wakes the screen using both ctypes mouse movement and pyautogui shift press.
"""
import ctypes
import sys
import time

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
    # Fail-safes
    pyautogui.FAILSAFE = False
except ImportError:
    PYAUTOGUI_AVAILABLE = False


def wake(show_summary: bool = False):
    """
    Wake the screen using mouse movement and keypress.
    If show_summary is True, opens the Action Center (Win+A).
    """
    if sys.platform != 'win32':
        print("  [WARNING] Not on Windows, skipping actual wake.")
        return

    # Method 1: ctypes mouse move (1 px and back)
    # 0x0001 is MOUSEEVENTF_MOVE
    ctypes.windll.user32.mouse_event(0x0001, 1, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.mouse_event(0x0001, -1, 0, 0, 0)

    # Method 2: pyautogui shift press
    if PYAUTOGUI_AVAILABLE:
        pyautogui.press('shift')
    
    if show_summary:
        if PYAUTOGUI_AVAILABLE:
            time.sleep(0.5) # Give screen time to wake
            pyautogui.hotkey('win', 'a')
        print("  [ACTION] Screen woken — showing notification summary")
    else:
        print("  [ACTION] Screen woken")

if __name__ == "__main__":
    wake(show_summary=True)

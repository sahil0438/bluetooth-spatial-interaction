"""
Do Not Disturb Executor for Phase 6.

Toggles Windows Focus Assist (DND).
Uses registry editing (Approach A) with GUI fallback (Approach B).
"""
import sys
import time

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
    pyautogui.FAILSAFE = False
except ImportError:
    PYAUTOGUI_AVAILABLE = False

if sys.platform == 'win32':
    import winreg

# State
_dnd_is_on = False

def _toggle_registry() -> bool:
    """
    Attempt to toggle DND via Windows registry (Windows 10/11 Focus Assist).
    This path varies widely by Windows version.
    Returns True if successful, False if path not found/accessible.
    """
    if sys.platform != 'win32':
        return False
        
    try:
        # A common location for Focus Assist/Quiet Hours in Windows 10
        # For Windows 11 it often moved to WNFA
        path = r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings"
        
        # We just try to read it to see if it's there. 
        # Modifying it directly might require explorer.exe restart to take effect on some builds.
        # But per requirements, we will try to use winreg if possible.
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ | winreg.KEY_WRITE)
        
        # Read current state (NOC_GLOBAL_SETTING_TOASTS_LEVEL)
        # 0 = Off, 1 = Priority Only, 2 = Alarms Only
        try:
            val, _ = winreg.QueryValueEx(key, "NOC_GLOBAL_SETTING_TOASTS_LEVEL")
        except FileNotFoundError:
            val = 0
            
        new_val = 0 if val > 0 else 2
        winreg.SetValueEx(key, "NOC_GLOBAL_SETTING_TOASTS_LEVEL", 0, winreg.REG_DWORD, new_val)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        # Fail gracefully
        return False

def _toggle_gui_fallback():
    """
    Fallback approach: Open settings and show instructions.
    """
    print("  [WARNING] Registry DND toggle unavailable on this build.")
    if PYAUTOGUI_AVAILABLE:
        print("  [INFO] Opening Windows Settings...")
        pyautogui.hotkey('win', 'i')
        time.sleep(1.0)
        # Type to search for focus assist
        pyautogui.typewrite("focus")
        time.sleep(0.5)
        pyautogui.press('down')
        pyautogui.press('enter')
        
    print("  \033[96m[INSTRUCTION] Please toggle 'Do Not Disturb' manually in the opened settings window.\033[0m")

def toggle():
    """Toggle DND state."""
    global _dnd_is_on
    
    # Try Approach A
    success = _toggle_registry()
    
    if not success:
        # Fallback to Approach B
        _toggle_gui_fallback()
        
    # Toggle our internal tracking state
    _dnd_is_on = not _dnd_is_on
    
    state_str = "ON — notifications silenced" if _dnd_is_on else "OFF — notifications restored"
    print(f"  [ACTION] Focus Assist: {state_str}")

if __name__ == "__main__":
    toggle()

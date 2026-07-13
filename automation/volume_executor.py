"""
Volume Executor for Phase 6.

Controls Windows master volume using pycaw.
"""
import sys
import ctypes

try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False


def _get_volume_interface():
    """Helper to get the pycaw volume interface."""
    if not PYCAW_AVAILABLE:
        return None
    try:
        devices = AudioUtilities.GetSpeakers()
        return devices.EndpointVolume
    except Exception as e:
        print(f"[ERROR] Failed to get audio interface: {e}")
        return None


def get_current_volume() -> float:
    """Returns current volume as float 0.0 to 1.0."""
    if not PYCAW_AVAILABLE:
        return 0.5
    try:
        volume_interface = _get_volume_interface()
        if volume_interface:
            return volume_interface.GetMasterVolumeLevelScalar()
    except Exception as e:
        print(f"[ERROR] Failed to get volume: {e}")
    return 0.5


def set_volume(level: float):
    """Sets volume to an absolute level (0.0 to 1.0). Clamped to 0.05-1.0."""
    if not PYCAW_AVAILABLE:
        print("[WARNING] pycaw not installed. Cannot set volume.")
        return
        
    level = max(0.05, min(1.0, level)) # Clamp
    try:
        volume_interface = _get_volume_interface()
        if volume_interface:
            volume_interface.SetMasterVolumeLevelScalar(level, None)
    except Exception as e:
        print(f"[ERROR] Failed to set volume: {e}")


def _print_volume_bar(old_level: float, new_level: float, direction: str):
    """Prints a nice ASCII progress bar for volume."""
    old_pct = int(old_level * 100)
    new_pct = int(new_level * 100)
    
    # Bar length 10
    filled = int(new_pct / 10)
    bar = "=" * filled + "-" * (10 - filled)
    
    arrow = "UP" if direction == "up" else "DOWN"
    print(f"  [ACTION] Volume: [{bar}] {new_pct}% ({arrow} from {old_pct}%)")


def adjust_volume(direction: str, steps: int) -> float:
    """
    Adjust volume up or down by step amount (5% per step).
    TODO: Determine rotation direction from signal shape.
    Currently defaults to 'up' due to Phase 4 limitations.
    """
    if not PYCAW_AVAILABLE:
        print("\n[ERROR] pycaw module not found!")
        print("Please install via: pip install pycaw comtypes")
        return 0.5

    # Phase 4 does not output direction yet, assume 'up' if not provided correctly, 
    # but handle 'down' if provided by testing tools
    if direction not in ("up", "down"):
        direction = "up"

    current = get_current_volume()
    delta = steps * 0.05
    
    if direction == "up":
        new_vol = current + delta
    else:
        new_vol = current - delta
        
    new_vol = max(0.05, min(1.0, new_vol))
    set_volume(new_vol)
    
    _print_volume_bar(current, new_vol, direction)
    return new_vol

if __name__ == "__main__":
    # Test
    v = adjust_volume("up", 2)

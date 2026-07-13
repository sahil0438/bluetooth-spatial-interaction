"""
Slide Executor for Phase 6.

Controls presentation slides via PyAutoGUI arrow keys.
"""
import time

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
    pyautogui.FAILSAFE = False
except ImportError:
    PYAUTOGUI_AVAILABLE = False

# State
_slide_counter = 1
_last_slide_time = 0.0
SLIDE_COOLDOWN = 0.3

def reset_counter():
    """Reset slide counter on presentation exit."""
    global _slide_counter
    _slide_counter = 1

def next_slide():
    """Press right arrow to advance slide."""
    global _slide_counter, _last_slide_time
    
    now = time.time()
    if now - _last_slide_time < SLIDE_COOLDOWN:
        return
        
    if PYAUTOGUI_AVAILABLE:
        pyautogui.press('right')
        
    _slide_counter += 1
    _last_slide_time = now
    print(f"  [ACTION] NEXT_SLIDE ---> (slide {_slide_counter} of ?)")

def prev_slide():
    """Press left arrow to go back."""
    global _slide_counter, _last_slide_time
    
    now = time.time()
    if now - _last_slide_time < SLIDE_COOLDOWN:
        return
        
    if PYAUTOGUI_AVAILABLE:
        pyautogui.press('left')
        
    _slide_counter = max(1, _slide_counter - 1)
    _last_slide_time = now
    print(f"  [ACTION] PREV_SLIDE <--- (slide {_slide_counter} of ?)")

if __name__ == "__main__":
    next_slide()
    next_slide()
    prev_slide()

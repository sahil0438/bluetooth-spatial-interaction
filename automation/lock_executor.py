"""
Lock Executor for Phase 6.

Handles screen locking via ctypes and context mode exiting.
"""
import ctypes
import time
import sys

def lock_with_delay(delay_seconds: int):
    """
    Lock the workstation, optionally with a countdown delay.
    """
    if delay_seconds > 0:
        print(f"  [ACTION] Locking screen in ", end="", flush=True)
        for i in range(delay_seconds, 0, -1):
            print(f"{i}... ", end="", flush=True)
            time.sleep(1)
        print("LOCKED")
    else:
        print("  [ACTION] Locking screen immediately... LOCKED")
        
    # Execute actual lock on Windows
    if sys.platform == 'win32':
        ctypes.windll.user32.LockWorkStation()
    else:
        print("  [WARNING] Not on Windows, skipping actual lock.")

def exit_special_mode(action_name: str):
    """
    Resets context for EXIT_PRESENTATION or EXIT_FOCUS.
    Does not lock screen.
    """
    print(f"  [ACTION] Exiting special mode: {action_name}")
    try:
        from context_engine.context_detector import reset_to_work_mode
        reset_to_work_mode(f"Manual exit via {action_name}")
    except ImportError:
        pass # Handle case where it's not implemented yet
    except AttributeError:
        print("  [WARNING] reset_to_work_mode not yet available in context_detector")

if __name__ == "__main__":
    # Test - do not lock in simple test unless passed arg
    if len(sys.argv) > 1 and sys.argv[1] == "--lock":
        lock_with_delay(3)
    else:
        print("Pass --lock to actually lock")

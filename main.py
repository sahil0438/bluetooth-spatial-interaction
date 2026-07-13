import argparse
import asyncio
import json
import sys
import threading
import time
from pathlib import Path

# Fix Windows console encoding — prevents 'charmap' codec errors with Unicode output
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from scanner.ble_scanner import BleScanner
from signal_processing.signal_pipeline import SignalPipeline
from signal_processing.terminal_visualizer import TerminalVisualizer
from bleak.exc import BleakBluetoothNotAvailableError

# Globals to coordinate background execution and cleanup
bg_loop = None
bg_thread = None
scanner_inst = None
pipeline_inst = None
recogniser_inst = None
async_tasks = []

def _print_banner():
    """Print startup banner showing all phases."""
    print("=" * 65)
    print("   BLUETOOTH SPATIAL INTERACTION SYSTEM")
    print("   Invisible User Interface — All Phases Active")
    print("=" * 65)
    print("   Phase 1: BLE Scanner .............. STARTING")
    print("   Phase 2: Signal Pipeline .......... STARTING")
    print("   Phase 3: Spatial Detection ........ STARTING")
    print("   Phase 4: Gesture Recognition ...... STARTING")
    print("   Phase 5: Context Awareness ........ STARTING")
    print("   Phase 6: Action Execution ......... STARTING")
    print("   Phase 7: PyQt6 Real-Time Dashboard  STARTING")
    print("=" * 65)


async def run_system_backend(target_name: str = None, target_address: str = None):
    global scanner_inst, pipeline_inst, recogniser_inst, async_tasks
    
    # Setup path variables using pathlib
    root_dir = Path(__file__).resolve().parent
    raw_log = root_dir / "logs" / "raw_scan.jsonl"
    filtered_log = root_dir / "logs" / "filtered_scan.jsonl"
    calibration_file = root_dir / "logs" / "calibration.json"

    # Truncate all log files to start fresh (prevents stale demo data showing in live mode)
    log_folder = root_dir / "logs"
    log_folder.mkdir(exist_ok=True)
    for name in ["raw_scan.jsonl", "filtered_scan.jsonl", "spatial_events.jsonl", 
                 "gesture_events.jsonl", "action_log.jsonl", "safety_blocks.jsonl", "context_events.jsonl"]:
        with open(log_folder / name, "w", encoding="utf-8") as f:
            f.write("")
    with open(log_folder / "session_summary.json", "w", encoding="utf-8") as f:
        json.dump({}, f)

    # Instantiate background components
    scanner_inst = BleScanner(target_name=target_name, target_address=target_address)
    pipeline_inst = SignalPipeline(raw_log, filtered_log, target_name=target_name, target_address=target_address)

    visualizer = TerminalVisualizer(filtered_log)
    visualizer.set_scanner(scanner_inst)

    # Initialize State Machine and Calibrator (Phase 3)
    from gesture_engine.state_machine import init_state_machine
    init_state_machine(root_dir / "logs")
    print("[OK] Phase 3: State machine initialized")

    from gesture_engine.calibrator import Calibrator
    calibrator = Calibrator(filtered_log, calibration_file)

    # Start scanner & pipeline
    scanner_task = asyncio.create_task(scanner_inst.run())
    pipeline_task = asyncio.create_task(pipeline_inst.run())
    async_tasks.extend([scanner_task, pipeline_task])
    print("[OK] Phase 1: BLE scanner started")
    print("[OK] Phase 2: Signal pipeline started")

    if not calibrator.is_calibrated():
        scanner_inst.render_enabled = False
        await asyncio.sleep(1.0)
        await calibrator.run_calibration(10.0)
        scanner_inst.render_enabled = True
    else:
        calibrator.load_calibration()

    # Initialize Gesture Recogniser (Phase 4)
    from gesture_engine.gesture_recogniser import init_recogniser
    try:
        recogniser_inst = init_recogniser()
        recogniser_task = asyncio.create_task(recogniser_inst.run(filtered_log))
        async_tasks.append(recogniser_task)
        print("[OK] Phase 4: Gesture recogniser started")
    except Exception as e:
        print(f"[WARNING] Phase 4: Could not start gesture recogniser ({e}). Continuing without.")

    # Initialize Context Pipeline (Phase 5)
    from context_engine.context_pipeline import run_context_pipeline
    context_task = asyncio.create_task(run_context_pipeline())
    async_tasks.append(context_task)
    print("[OK] Phase 5: Context pipeline started")

    # Initialize Automation Layer (Phase 6)
    try:
        import pycaw
        print("[OK] Phase 6: Automation layer started (pycaw available)")
    except ImportError:
        print("[WARNING] Phase 6: pycaw not found. Volume control will be disabled.")

    # Start the terminal visualizer (runs in background)
    visualizer_task = asyncio.create_task(visualizer.run())
    async_tasks.append(visualizer_task)

    # Start target change monitor (watches for UI device selection changes)
    target_change_file = root_dir / "logs" / "target_change.json"
    monitor_task = asyncio.create_task(
        _target_change_monitor(target_change_file, scanner_inst, pipeline_inst)
    )
    async_tasks.append(monitor_task)

    print("\n[INFO] Backend services running in background thread.\n")
    
    # Keep running until cancelled
    try:
        await asyncio.gather(*async_tasks)
    except asyncio.CancelledError:
        pass


async def _target_change_monitor(change_file: Path, scanner, pipeline):
    """
    Watches logs/target_change.json for device selection changes from the dashboard.
    When the user picks a different device in the UI combo box, this updates the
    scanner and pipeline targets at runtime.
    """
    last_mtime = 0.0
    while True:
        await asyncio.sleep(1.0)
        try:
            if not change_file.exists():
                continue
            mtime = change_file.stat().st_mtime
            if mtime <= last_mtime:
                continue
            last_mtime = mtime
            with open(change_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            new_name = data.get("target_name")
            new_addr = data.get("target_address")
            if new_name and scanner:
                scanner.target_name = new_name
                scanner.target_address = new_addr.upper() if new_addr else None
                print(f"[INFO] Scanner target updated to: {new_name}")
            if new_name and pipeline:
                pipeline.target_name = new_name
                pipeline.target_address = new_addr.upper() if new_addr else None
        except (json.JSONDecodeError, OSError):
            pass
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[WARNING] Target change monitor error: {e}")


async def shutdown_backend():
    global scanner_inst, pipeline_inst, recogniser_inst, async_tasks
    print("\nShutting down backend services...")
    
    if scanner_inst:
        scanner_inst.stop()
    if pipeline_inst and pipeline_inst.device_filter:
        pipeline_inst.device_filter.stop()
    if recogniser_inst:
        recogniser_inst.stop()

    # Phase 5 shutdown — save session summary
    try:
        from context_engine.context_pipeline import stop_pipeline
        from context_engine import session_tracker
        stop_pipeline()
        # Guard against interpreter shutdown where builtins (like 'open') are cleared
        import builtins
        if hasattr(builtins, 'open'):
            session_tracker.save_summary()
            print("[OK] Session summary saved.")
    except Exception as e:
        print(f"[WARNING] Could not save session summary: {e}")

    # Cancel tasks
    for task in async_tasks:
        if not task.done():
            task.cancel()
            
    if async_tasks:
        await asyncio.gather(*async_tasks, return_exceptions=True)
    print("Backend services stopped.")


def run_background_loop(loop, target_name, target_address):
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_system_backend(target_name, target_address))
    except BleakBluetoothNotAvailableError:
        print("\n[ERROR] Bluetooth Radio is powered off. Enable Bluetooth to run live mode.")
    except Exception as e:
        print(f"[ERROR] Background thread error: {e}")


def main():
    global bg_loop, bg_thread
    
    parser = argparse.ArgumentParser(
        description="Bluetooth-Based Invisible User Interface - Spatial Computing Signal Processor"
    )
    parser.add_argument(
        "--target-name",
        type=str,
        default="Nothing Phone (2a)",
        help="Specify the Bluetooth device name to track (default: Nothing Phone (2a))"
    )
    parser.add_argument(
        "--target-address",
        type=str,
        default=None,
        help="Specify the Bluetooth device address (MAC) to track (e.g., 28:D2:5E:D7:C0:4B)"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run dashboard in simulation mode without active BLE scanner"
    )
    args = parser.parse_args()

    # Print startup banner
    _print_banner()

    from PyQt6.QtWidgets import QApplication
    from ui.dashboard import MainWindow

    # Initialize PyQt6 App
    app = QApplication(sys.argv)
    
    if args.demo:
        print("[INFO] Starting in DEMO simulation mode...")
        window = MainWindow(is_demo_only=True)
        window.show()
        sys.exit(app.exec())
    else:
        print(f"[INFO] Starting in LIVE mode. Target device name: '{args.target_name}'")
        if args.target_address:
            print(f"[INFO] Target device address: {args.target_address}")
            
        # Start backend event loop in background thread
        bg_loop = asyncio.new_event_loop()
        bg_thread = threading.Thread(
            target=run_background_loop,
            args=(bg_loop, args.target_name, args.target_address),
            daemon=True
        )
        bg_thread.start()
        
        # Open Dashboard window on the main thread
        window = MainWindow(is_demo_only=False)
        window.show()
        
        # Block until the GUI is closed
        exit_code = app.exec()
        
        # Shutdown backend tasks thread-safely
        if bg_loop and bg_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(shutdown_backend(), bg_loop)
            try:
                future.result(timeout=5.0)
            except Exception as e:
                print(f"[WARNING] Shutdown wait timeout/error: {e}")
            bg_loop.call_soon_threadsafe(bg_loop.stop)
            
        sys.exit(exit_code)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    main()

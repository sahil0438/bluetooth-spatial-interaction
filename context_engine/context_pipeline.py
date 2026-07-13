"""
Context Event Pipeline for Phase 5 — Context Awareness Engine.

The async orchestrator that connects everything:
  1. Tails logs/gesture_events.jsonl for new gesture events
  2. Evaluates context on each gesture + every 2 seconds
  3. Resolves gestures to actions via action_resolver
  4. Updates session_tracker
  5. Passes action dicts to Phase 6 executor (stub until Phase 6 is built)

Usage:
    Called from main.py:
        from context_engine.context_pipeline import run_context_pipeline
        asyncio.create_task(run_context_pipeline())

Exports:
    async def run_context_pipeline()
    def stop_pipeline()
"""
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

from . import context_detector
from . import action_resolver
from . import session_tracker

# Paths
ROOT_DIR = Path(__file__).parent.parent
GESTURE_LOG = ROOT_DIR / "logs" / "gesture_events.jsonl"

# How often to re-evaluate context even without gestures (seconds)
CONTEXT_EVAL_INTERVAL = 2.0

# Module-level running flag
_running = False
_last_context = "WORK_MODE"


async def _tail_gesture_log():
    """
    Tail gesture_events.jsonl and process each new gesture event.
    """
    global _running, _last_context

    # Wait until gesture log file exists
    while _running and not GESTURE_LOG.exists():
        await asyncio.sleep(1.0)

    if not _running:
        return

    with open(GESTURE_LOG, "r", encoding="utf-8") as f:
        # Seek to end — only process NEW events
        f.seek(0, 2)

        while _running:
            line = f.readline()
            if not line:
                await asyncio.sleep(0.1)
                continue

            try:
                gesture_event = json.loads(line.strip())
            except (json.JSONDecodeError, TypeError):
                continue

            gesture_name = gesture_event.get("gesture", "")

            # Skip IDLE if it somehow appears (should never happen per Phase 4)
            if gesture_name == "IDLE":
                continue

            # 1. Feed gesture to context detector
            context_detector.record_gesture(gesture_event)

            # 2. Evaluate context immediately
            current_context = context_detector.evaluate()

            # 3. Track context change in session
            if current_context != _last_context:
                session_tracker.update_context(current_context)
                _last_context = current_context

            # 4. Resolve gesture → action
            action_dict = action_resolver.resolve(gesture_event, current_context)

            # 5. Record in session tracker
            session_tracker.record_gesture(gesture_name)
            session_tracker.record_action(action_dict)

            # 6. Pass to Phase 6 executor (stub)
            _execute_action(action_dict)
            
            # Save immediately
            session_tracker.save_summary()


async def _periodic_context_eval():
    """
    Background loop: re-evaluate context every 2 seconds.
    Catches AWAY_MODE and FOCUS_MODE transitions that happen
    without any gesture events.
    """
    global _running, _last_context

    while _running:
        await asyncio.sleep(CONTEXT_EVAL_INTERVAL)

        if not _running:
            break

        current_context = context_detector.evaluate()

        if current_context != _last_context:
            session_tracker.update_context(current_context)
            _last_context = current_context
        
        # Periodically save summary to update duration timers in real-time
        session_tracker.save_summary()


async def _session_auto_save():
    """Background loop: auto-save session summary periodically."""
    global _running

    tracker = session_tracker._get_tracker()
    while _running:
        await asyncio.sleep(10)  # fast backup interval
        if _running:
            tracker.save_summary()


def _execute_action(action_dict: dict):
    """
    Phase 6 executor stub.
    
    In Phase 6, this will import and call the actual automation executor.
    For now, it just acknowledges the action.
    """
    action = action_dict.get("action", "NO_ACTION")
    if action == "NO_ACTION":
        return

    # Phase 6 Action Execution
    try:
        from automation.action_executor import execute
        executed = execute(action_dict)
        
        # Track safety blocks
        if not executed:
            session_tracker.record_safety_block()
            
        # Track volume changes if applicable
        try:
            from automation.volume_executor import get_current_volume
            vol = int(get_current_volume() * 100)
            session_tracker.update_volume(vol)
        except Exception:
            pass
            
    except ImportError:
        pass # Automation module not built yet


async def run_context_pipeline():
    """
    Main entry point: start all context pipeline coroutines.
    Runs until stop_pipeline() is called.
    """
    global _running, _last_context
    _running = True

    # Initialize singletons
    context_detector.init_detector()
    tracker = session_tracker.init_tracker()
    _last_context = context_detector.get_current_context()

    print("[INFO] Context pipeline started (Phase 5)")

    # Run all three loops concurrently
    try:
        await asyncio.gather(
            _tail_gesture_log(),
            _periodic_context_eval(),
            _session_auto_save(),
        )
    except asyncio.CancelledError:
        pass
    finally:
        # Final save on shutdown
        session_tracker.stop()
        print("[INFO] Context pipeline stopped. Session summary saved.")


def stop_pipeline():
    """Stop all pipeline loops."""
    global _running
    _running = False


if __name__ == "__main__":
    print("=" * 60)
    print("  Context Pipeline — Phase 5 Module Check")
    print("=" * 60)
    print(f"  Gesture log path: {GESTURE_LOG}")
    print(f"  Eval interval:    {CONTEXT_EVAL_INTERVAL}s")
    print("  Context pipeline module loaded successfully.")

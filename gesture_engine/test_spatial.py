import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from gesture_engine.state_machine import StateMachineManager

def run_tests():
    root_dir = Path(__file__).parent.parent
    test_log_dir = root_dir / "logs" / "test_logs"
    
    # Ensure fresh test log directory
    if test_log_dir.exists():
        shutil.rmtree(test_log_dir)
    test_log_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("               SPATIAL INTERPRETATION STATE MACHINE TESTS")
    print("=" * 70)

    # ----------------------------------------------------
    # TEST 1: Approach Sequence
    # ----------------------------------------------------
    print("\n--- Running Test 1: Approach Sequence ---")
    manager = StateMachineManager(test_log_dir)
    # Start at ABSENT
    manager.current_state = {
        "state": "ABSENT",
        "confidence": 100.0,
        "rssi": -105.0,
        "timestamp": datetime.now().isoformat(),
        "slope": 0.0,
        "trend_direction": "STABLE"
    }
    manager.last_state_change_time = 0.0  # Allow immediate first transition
    
    rssi_seq_1 = [-85, -80, -74, -68, -62, -57, -52, -48, -45, -42]
    base_time = datetime.now()
    
    states_visited = []
    for i, rssi in enumerate(rssi_seq_1):
        ts = (base_time + timedelta(seconds=i)).isoformat()
        res = manager.update(rssi, ts, "tracking")
        states_visited.append(manager.current_state["state"])
    
    final_state = manager.current_state["state"]
    passed = (final_state == "APPROACHING")
    status = "PASS" if passed else "FAIL"
    print(f"Test 1 result: {status} (Final State: {final_state}, Visited: {list(dict.fromkeys(states_visited))})")

    # ----------------------------------------------------
    # TEST 2: Departure Sequence
    # ----------------------------------------------------
    print("\n--- Running Test 2: Departure Sequence ---")
    manager = StateMachineManager(test_log_dir)
    # Manually initialize to PRESENT_STABLE
    manager.current_state = {
        "state": "PRESENT_STABLE",
        "confidence": 100.0,
        "rssi": -40.0,
        "timestamp": datetime.now().isoformat(),
        "slope": 0.0,
        "trend_direction": "STABLE"
    }
    base_time = datetime.now()
    manager.last_state_change_time = base_time.timestamp() - 5.0  # Set change time in the past to allow transition
    manager.last_seen_time = base_time.timestamp()
    
    rssi_seq_2 = [-42, -48, -54, -60, -67, -73, -80, -87, -95, -102]
    
    states_visited = []
    for i, rssi in enumerate(rssi_seq_2):
        ts = (base_time + timedelta(seconds=i)).isoformat()
        res = manager.update(rssi, ts, "tracking")
        states_visited.append(manager.current_state["state"])
        
    final_state = manager.current_state["state"]
    # Should transition to DEPARTING first, and then to ABSENT once RSSI is below -100
    passed = ("DEPARTING" in states_visited and final_state == "ABSENT")
    status = "PASS" if passed else "FAIL"
    print(f"Test 2 result: {status} (Final State: {final_state}, Visited: {list(dict.fromkeys(states_visited))})")

    # ----------------------------------------------------
    # TEST 3: Stable Presence
    # ----------------------------------------------------
    print("\n--- Running Test 3: Stable Presence ---")
    manager = StateMachineManager(test_log_dir)
    # Manually initialize to APPROACHING to satisfy transition graph ABSENT -> APPROACHING -> PRESENT_STABLE
    manager.current_state = {
        "state": "APPROACHING",
        "confidence": 100.0,
        "rssi": -75.0,
        "timestamp": datetime.now().isoformat(),
        "slope": 2.0,
        "trend_direction": "APPROACHING"
    }
    base_time = datetime.now()
    manager.last_state_change_time = base_time.timestamp() - 5.0
    manager.last_seen_time = base_time.timestamp()
    
    rssi_seq_3 = [-58, -60, -57, -61, -59, -58, -62, -60, -57, -59]
    
    states_visited = []
    for i, rssi in enumerate(rssi_seq_3):
        ts = (base_time + timedelta(seconds=i)).isoformat()
        res = manager.update(rssi, ts, "tracking")
        states_visited.append(manager.current_state["state"])
        
    final_state = manager.current_state["state"]
    passed = (final_state == "PRESENT_STABLE")
    status = "PASS" if passed else "FAIL"
    print(f"Test 3 result: {status} (Final State: {final_state}, Visited: {list(dict.fromkeys(states_visited))})")

    # ----------------------------------------------------
    # TEST 4: Rapid Approach
    # ----------------------------------------------------
    print("\n--- Running Test 4: Rapid Approach ---")
    manager = StateMachineManager(test_log_dir)
    # Manually initialize to PRESENT_STABLE (RAPID_APPROACH is only valid from PRESENT_STABLE)
    manager.current_state = {
        "state": "PRESENT_STABLE",
        "confidence": 100.0,
        "rssi": -85.0,
        "timestamp": datetime.now().isoformat(),
        "slope": 0.0,
        "trend_direction": "STABLE"
    }
    base_time = datetime.now()
    manager.last_state_change_time = base_time.timestamp() - 5.0
    manager.last_seen_time = base_time.timestamp()
    
    rssi_seq_4 = [-90, -88, -85, -65, -45, -42, -40, -41, -42, -43]
    
    states_visited = []
    for i, rssi in enumerate(rssi_seq_4):
        ts = (base_time + timedelta(seconds=i)).isoformat()
        res = manager.update(rssi, ts, "tracking")
        states_visited.append(manager.current_state["state"])
        
    final_state = manager.current_state["state"]
    # Should transition into RAPID_APPROACH, then automatically fall back to PRESENT_STABLE after 2s
    passed = ("RAPID_APPROACH" in states_visited and final_state == "PRESENT_STABLE")
    status = "PASS" if passed else "FAIL"
    print(f"Test 4 result: {status} (Final State: {final_state}, Visited: {list(dict.fromkeys(states_visited))})")

    # ----------------------------------------------------
    # TEST 5: Absent (phone out of range)
    # ----------------------------------------------------
    print("\n--- Running Test 5: Absent (out of range) ---")
    manager = StateMachineManager(test_log_dir)
    manager.current_state = {
        "state": "PRESENT_STABLE",
        "confidence": 100.0,
        "rssi": -80.0,
        "timestamp": datetime.now().isoformat(),
        "slope": 0.0,
        "trend_direction": "STABLE"
    }
    base_time = datetime.now()
    manager.last_state_change_time = base_time.timestamp() - 5.0
    manager.last_seen_time = base_time.timestamp()
    
    rssi_seq_5 = [-80, -90, -100, -110, -120, -127, -127, -127, -127, -127]
    
    states_visited = []
    for i, rssi in enumerate(rssi_seq_5):
        ts = (base_time + timedelta(seconds=i)).isoformat()
        res = manager.update(rssi, ts, "tracking")
        states_visited.append(manager.current_state["state"])
        
    final_state = manager.current_state["state"]
    passed = ("DEPARTING" in states_visited and final_state == "ABSENT")
    status = "PASS" if passed else "FAIL"
    print(f"Test 5 result: {status} (Final State: {final_state}, Visited: {list(dict.fromkeys(states_visited))})")

    # Clean up test logs directory
    try:
        shutil.rmtree(test_log_dir)
    except Exception:
        pass

    print("=" * 70)

if __name__ == "__main__":
    run_tests()

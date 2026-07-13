"""Scan and display ALL available BLE devices nearby."""
import asyncio
import sys
from bleak import BleakScanner

async def scan():
    print("Scanning for ALL BLE devices for 15 seconds...\n")
    
    all_devices = {}
    
    def callback(device, adv_data):
        addr = device.address.upper()
        name = device.name or adv_data.local_name or "Unknown"
        rssi = adv_data.rssi
        mfg = list(adv_data.manufacturer_data.keys())
        
        # Keep updating to get the best name and latest RSSI
        if addr not in all_devices or name != "Unknown":
            all_devices[addr] = {"name": name, "rssi": rssi, "mfg_keys": mfg}
    
    scanner = BleakScanner(detection_callback=callback)
    async with scanner:
        await asyncio.sleep(15)
    
    # Display results
    print(f"{'='*65}")
    print(f" Found {len(all_devices)} BLE device(s)")
    print(f"{'='*65}\n")
    
    if not all_devices:
        print("No devices found. Make sure Bluetooth is enabled.")
        return
    
    # Separate named and unknown devices
    named = {k: v for k, v in all_devices.items() if v["name"] != "Unknown"}
    unknown = {k: v for k, v in all_devices.items() if v["name"] == "Unknown"}
    
    # Show named devices first, sorted by RSSI (strongest first)
    if named:
        print(f"--- Named Devices ({len(named)}) ---")
        sorted_named = sorted(named.items(), key=lambda x: x[1]["rssi"], reverse=True)
        for i, (addr, info) in enumerate(sorted_named, 1):
            print(f"  {i:3d}. {info['name']:30s} | {addr} | RSSI: {info['rssi']:4d} dBm | Mfg: {info['mfg_keys']}")
    
    # Show unknown devices, sorted by RSSI
    if unknown:
        print(f"\n--- Unknown Devices ({len(unknown)}) ---")
        sorted_unknown = sorted(unknown.items(), key=lambda x: x[1]["rssi"], reverse=True)
        for i, (addr, info) in enumerate(sorted_unknown, 1):
            print(f"  {i:3d}. {addr} | RSSI: {info['rssi']:4d} dBm | Mfg: {info['mfg_keys']}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(scan())

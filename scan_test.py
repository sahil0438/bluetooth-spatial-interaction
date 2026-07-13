"""Development utility — not part of main pipeline"""
"""Quick BLE scan to list all named devices nearby."""
import asyncio
import sys
from bleak import BleakScanner

async def scan():
    print("Scanning for BLE devices for 15 seconds...")
    print("Make sure your phone is in discoverable/pairing mode!\n")
    
    devices_seen = {}
    
    def callback(device, adv_data):
        name = device.name or adv_data.local_name
        if name and device.address not in devices_seen:
            devices_seen[device.address] = {
                "name": name,
                "rssi": adv_data.rssi,
                "address": device.address,
            }
            print(f"  Found: {name:30s} | Address: {device.address} | RSSI: {adv_data.rssi} dBm")
    
    scanner = BleakScanner(detection_callback=callback)
    async with scanner:
        await asyncio.sleep(15)
    
    print(f"\n--- Scan complete. Found {len(devices_seen)} named device(s). ---")
    if not devices_seen:
        print("No named devices found. Make sure your phone is discoverable.")
    else:
        print("\nAll named devices:")
        for addr, info in sorted(devices_seen.items(), key=lambda x: x[1]['rssi'], reverse=True):
            print(f"  {info['name']:30s} | {addr} | RSSI: {info['rssi']} dBm")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(scan())

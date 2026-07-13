"""Identify your phone by toggling Bluetooth on/off and comparing scan results."""
import asyncio
import sys
from bleak import BleakScanner

async def scan_devices(duration=10):
    """Returns a dict of {address: {name, rssi, mfg_keys}}"""
    devices = {}
    def callback(device, adv_data):
        addr = device.address.upper()
        name = device.name or adv_data.local_name or "unnamed"
        rssi = adv_data.rssi
        mfg = list(adv_data.manufacturer_data.keys())
        # Keep updating to get latest RSSI
        devices[addr] = {"name": name, "rssi": rssi, "mfg_keys": mfg}
    
    scanner = BleakScanner(detection_callback=callback)
    async with scanner:
        await asyncio.sleep(duration)
    return devices

async def main():
    # Phase 1: Scan with phone Bluetooth OFF
    print("=" * 60)
    print("STEP 1: Turn OFF Bluetooth on your Nothing Phone (2a)")
    print("=" * 60)
    input("Press ENTER when Bluetooth is OFF on your phone...")
    
    print("\nScanning for 10 seconds (phone BT OFF)...")
    devices_off = await scan_devices(10)
    print(f"Found {len(devices_off)} devices with phone OFF.\n")
    
    # Phase 2: Scan with phone Bluetooth ON
    print("=" * 60)
    print("STEP 2: Turn ON Bluetooth on your Nothing Phone (2a)")
    print("=" * 60)
    input("Press ENTER when Bluetooth is ON on your phone...")
    
    print("\nScanning for 10 seconds (phone BT ON)...")
    devices_on = await scan_devices(10)
    print(f"Found {len(devices_on)} devices with phone ON.\n")
    
    # Phase 3: Find the difference
    new_devices = {}
    for addr, info in devices_on.items():
        if addr not in devices_off:
            new_devices[addr] = info
    
    print("=" * 60)
    print("RESULTS: New devices that appeared when phone was turned ON")
    print("=" * 60)
    
    if not new_devices:
        print("No new devices detected. The phone might be using an")
        print("address that was already present. Try again with the")
        print("phone further away from other devices.")
    else:
        # Sort by RSSI (strongest first)
        sorted_new = sorted(new_devices.items(), key=lambda x: x[1]["rssi"], reverse=True)
        for i, (addr, info) in enumerate(sorted_new, 1):
            print(f"  {i}. Address: {addr} | RSSI: {info['rssi']} dBm | Name: {info['name']} | Mfg: {info['mfg_keys']}")
        
        print(f"\nYour phone is most likely #{1} (strongest signal).")
        print(f"Address: {sorted_new[0][0]}")
        print(f"\nNote: This address will change periodically (Android MAC randomization).")
        print(f"Manufacturer IDs: {sorted_new[0][1]['mfg_keys']}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

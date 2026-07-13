"""Classic Bluetooth scan to discover devices by name."""
import sys

try:
    from btpy import ClassicDevice
    print("Scanning for Classic Bluetooth devices (this takes ~10 seconds)...")
    print("Make sure your phone is in discoverable mode!\n")
    
    results = ClassicDevice.scan(10)
    
    if results:
        print(f"\n--- Found {len(results)} device(s) ---")
        for device in results:
            print(f"  {device}")
    else:
        print("\nNo classic Bluetooth devices found.")
        print("Make sure your phone's Bluetooth is on and set to 'Visible to other devices'.")
except ImportError as e:
    print(f"Import error: {e}")
except Exception as e:
    print(f"Error during scan: {type(e).__name__}: {e}")
    
    # Fallback: try using bumble directly or Windows APIs
    print("\nTrying alternative approach with Windows Bluetooth APIs...")
    try:
        import asyncio
        import winrt.windows.devices.bluetooth as bt
        import winrt.windows.devices.enumeration as de
        
        async def classic_scan():
            selector = bt.BluetoothDevice.get_device_selector()
            devices = await de.DeviceInformation.find_all_async(selector)
            print(f"\nFound {devices.size} paired/cached Bluetooth devices:")
            for i in range(devices.size):
                d = devices.get_at(i)
                print(f"  Name: {d.name}  |  ID: {d.id}")
        
        asyncio.run(classic_scan())
    except Exception as e2:
        print(f"Alternative also failed: {type(e2).__name__}: {e2}")

#!/usr/bin/env python3
"""Scan for the Arcade Coder over BLE."""
import asyncio

from bleak import BleakScanner

SERVICE_UUID = "778d5426-fa29-4363-91fd-a9f5cfcfce85"


async def main() -> None:
    devices = await BleakScanner.discover(timeout=8.0, return_adv=True)
    for address, (device, adv) in devices.items():
        name = device.name or adv.local_name or ""
        uuids = [u.lower() for u in (adv.service_uuids or [])]
        likely = SERVICE_UUID in uuids or "arcade" in name.lower() or "coder" in name.lower()
        marker = "*" if likely else " "
        print(f"{marker} {address}  RSSI={adv.rssi}  {name or '(unnamed)'}  uuids={uuids}")


if __name__ == "__main__":
    asyncio.run(main())

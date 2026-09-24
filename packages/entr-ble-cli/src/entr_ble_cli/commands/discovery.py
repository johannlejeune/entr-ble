import argparse

from bleak import BleakScanner

from entr_ble import advertising


def register(sub):
    p = sub.add_parser("scan", help="find nearby ENTR locks")
    p.add_argument("--all", action="store_true", help="also list non-ENTR BLE devices")
    p.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="scan duration in seconds (default: 5)",
    )

    return {
        "scan": scan,
    }


async def scan(args: argparse.Namespace) -> None:
    found = await BleakScanner.discover(timeout=args.timeout, return_adv=True)
    locks, others = [], []
    for address, (device, adv) in found.items():
        lock = advertising.parse_advertisement(address, adv)
        if lock is not None:
            locks.append(lock)
        else:
            others.append((address, device.name or "?"))
    for lock in sorted(locks, key=lambda x: -x.rssi):
        print(
            f"{lock.address} ENTR name={lock.name} state={lock.state_name} rssi={lock.rssi}"
        )
    if not locks:
        print("no ENTR lock found")
    if args.all:
        for address, name in sorted(others):
            print(f"{address} {name}")
    elif others:
        print(f"({len(others)} other BLE devices hidden, use --all to show them)")

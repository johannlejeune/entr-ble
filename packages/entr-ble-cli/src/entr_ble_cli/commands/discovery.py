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


async def scan(timeout: float = 5.0, show_all: bool = False) -> list[str]:
    found = await BleakScanner.discover(timeout=timeout, return_adv=True)
    locks = []
    others = []
    for address, (device, adv) in found.items():
        lock = advertising.parse_advertisement(address, adv)
        if lock is None:
            others.append((address, f"{address} {device.name or '?'}"))
        else:
            locks.append(
                (
                    lock.rssi,
                    f"{address} ENTR name={lock.name} state={lock.state_name} rssi={lock.rssi}",
                )
            )
    locks.sort(key=lambda item: -(item[0] if item[0] is not None else -1000))
    others.sort()
    lock_lines = [label for _, label in locks]
    other_lines = [label for _, label in others]
    lines = lock_lines or ["no ENTR lock found"]
    if show_all:
        lines.extend(other_lines)
    elif other_lines:
        lines.append(
            f"({len(other_lines)} other BLE devices hidden, use --all to show them)"
        )
    return lines

from dataclasses import dataclass

from bleak import BleakScanner

from entr_ble import advertising


@dataclass(frozen=True)
class ScanItem:
    address: str
    label: str
    is_lock: bool
    rssi: int | None = None


async def discover(timeout: float = 5.0) -> list[ScanItem]:
    found = await BleakScanner.discover(timeout=timeout, return_adv=True)
    locks, others = [], []
    for address, (device, adv) in found.items():
        lock = advertising.parse_advertisement(address, adv)
        if lock is None:
            others.append(ScanItem(address, f"{address} {device.name or '?'}", False))
        else:
            locks.append(
                ScanItem(
                    address,
                    f"{address} ENTR name={lock.name} state={lock.state_name} rssi={lock.rssi}",
                    True,
                    lock.rssi,
                )
            )
    return sorted(
        locks, key=lambda item: -(item.rssi if item.rssi is not None else -1000)
    ) + sorted(others, key=lambda item: item.address)


async def scan(timeout: float = 5.0, show_all: bool = False) -> list[str]:
    items = await discover(timeout)
    locks = [item.label for item in items if item.is_lock]
    others = [item.label for item in items if not item.is_lock]
    lines = locks or ["no ENTR lock found"]
    if show_all:
        lines.extend(others)
    elif others:
        lines.append(
            f"({len(others)} other BLE devices hidden, use --all to show them)"
        )
    return lines

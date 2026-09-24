import argparse
from collections.abc import Mapping

from .common import session


def register(sub):
    p = sub.add_parser("status", help="show lock/door/battery status")
    p.add_argument("address")
    p.add_argument(
        "--raw", action="store_true", help="also print the undecoded response bytes"
    )

    p = sub.add_parser("info", help="show serial number and firmware variant")
    p.add_argument("address")
    p.add_argument(
        "--raw", action="store_true", help="also print the undecoded response bytes"
    )

    p = sub.add_parser(
        "device-info", help="model, device id and BLE/MCU/radio firmware versions"
    )
    p.add_argument("address")
    p.add_argument(
        "--raw", action="store_true", help="also print the undecoded response bytes"
    )

    return {
        "status": status,
        "info": info,
        "device-info": device_info,
    }


async def status(args: argparse.Namespace) -> None:
    client, _creds = await session(args.address)
    try:
        config = await client.get_device_config()
        _print_fields(config, args.raw)
    finally:
        await client.disconnect()


async def info(args: argparse.Namespace) -> None:
    client, _creds = await session(args.address)
    try:
        info = await client.get_lock_sn()
        _print_fields(info, args.raw)
        print(f"comm_version: {client.comm_version}")
    finally:
        await client.disconnect()


async def device_info(args: argparse.Namespace) -> None:
    client, _creds = await session(args.address)
    try:
        info = await client.get_device_info()
        _print_fields(info, args.raw)
    finally:
        await client.disconnect()


def _print_fields(fields: Mapping[str, object], show_raw: bool) -> None:
    """The undecoded response bytes are only useful when cross-checking the
    decoding itself, so they stay out of the way unless asked for."""
    for key, value in fields.items():
        if key == "raw" and not show_raw:
            continue
        print(f"{key}: {value}")

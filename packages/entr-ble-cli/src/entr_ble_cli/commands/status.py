from .common import handle


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
        name: handle
        for name in (
            "status",
            "info",
            "device-info",
        )
    }

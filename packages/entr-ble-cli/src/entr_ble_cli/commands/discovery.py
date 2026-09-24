from .common import handle


def register(sub):
    p = sub.add_parser("scan", help="find nearby ENTR locks")
    p.add_argument("--all", action="store_true", help="also list non-ENTR BLE devices")
    p.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="scan duration in seconds (default: 5)",
    )

    return {name: handle for name in ("scan",)}

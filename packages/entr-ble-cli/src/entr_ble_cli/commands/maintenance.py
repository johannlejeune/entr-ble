from .common import handle


def register(sub):
    p = sub.add_parser(
        "calibrate",
        help="run the mechanical calibration (uninitialized or erratic locks)",
    )
    p.add_argument("address")
    p.add_argument("admin_code")
    p.add_argument(
        "--door",
        choices=["left", "right"],
        default="left",
        help="door opening direction (default: left)",
    )
    p.add_argument(
        "--type",
        choices=["normal", "lift"],
        default="normal",
        help="lock type (default: normal)",
    )

    p = sub.add_parser(
        "magnet-calibrate", help="teach the lock the door magnet position"
    )
    p.add_argument("address")
    p.add_argument("admin_code")

    p = sub.add_parser("factory-reset", help="wipe every user and setting on the lock")
    p.add_argument("address")
    p.add_argument("admin_code")
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")

    p = sub.add_parser("set-time", help="set the lock clock to current UTC time")
    p.add_argument("address")

    p = sub.add_parser("audit-trail", help="dump the event log (NIZ firmware)")
    p.add_argument("address")
    p.add_argument(
        "admin_code",
        nargs="?",
        default=None,
        help="defaults to the factory audit code Aa1111",
    )

    p = sub.add_parser(
        "get-errors", help="dump the firmware fault log (empty on ENTR EURO)"
    )
    p.add_argument("address")
    p.add_argument(
        "--query",
        default="00" * 8,
        help="8-byte query hex, meaning unknown, ignored by the lock (default: zeros)",
    )
    p.add_argument(
        "--raw", action="store_true", help="also print the undecoded response bytes"
    )

    return {
        name: handle
        for name in (
            "calibrate",
            "magnet-calibrate",
            "factory-reset",
            "set-time",
            "audit-trail",
            "get-errors",
        )
    }

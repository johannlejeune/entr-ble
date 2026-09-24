from .common import handle


def register(sub):
    p = sub.add_parser(
        "set-owner",
        help="first-time setup of an uninitialized lock (factory admin code 000000 replaced)",
    )
    p.add_argument("address")
    p.add_argument("admin_code", help="the new owner password, 6 characters")
    p.add_argument(
        "--name",
        required=True,
        help="lock name, shown in advertisements (12 bytes max)",
    )
    p.add_argument(
        "--user",
        default="owner",
        help="owner user name, also its identifier (default: owner)",
    )
    p.add_argument(
        "--provider",
        type=int,
        default=4,
        help="brand id: Mul-T-Lock 1, Yale 2, Nemef 3, Vachette 4, Tesa 5, ASSA 6 (default: 4)",
    )
    p.add_argument(
        "--sync-time",
        action="store_true",
        help="also set the lock clock (NIZ firmware only)",
    )

    p = sub.add_parser(
        "enroll",
        help="claim the single owner slot, revoking whichever device currently holds it",
    )
    p.add_argument("address")
    p.add_argument("admin_code", help="the owner password, 6 characters")
    p.add_argument("--name", help="lock name, stored for later settings commands")

    p = sub.add_parser(
        "activate", help="redeem a key an owner created for this computer"
    )
    p.add_argument("address")
    p.add_argument("key_code", help="6-character key code supplied by an owner")

    return {
        name: handle
        for name in (
            "set-owner",
            "enroll",
            "activate",
        )
    }

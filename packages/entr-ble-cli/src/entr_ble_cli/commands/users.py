from entr_ble import const

from ..shared import ROLE_CHOICES
from .common import handle


def register(sub):
    p = sub.add_parser(
        "list-users", help="list users, including ones still pending activation"
    )
    p.add_argument("address")
    p.add_argument("admin_code")

    p = sub.add_parser(
        "create-user", help="create a pending user and print its key code"
    )
    p.add_argument("address")
    p.add_argument("admin_code")
    p.add_argument("name", help="user name, also its identifier (16 chars max)")
    p.add_argument(
        "--role",
        choices=ROLE_CHOICES,
        default="user",
        help="user, admin, or a radio accessory (remote-control/wall-reader/integration-unit)",
    )
    p.add_argument(
        "--expiration",
        type=int,
        default=3,
        choices=const.EXPIRATION_HOURS,
        help="hours the key code stays redeemable (default: 3)",
    )
    p.add_argument("--code", help="use this key code instead of generating one")

    p = sub.add_parser(
        "set-admin-code", help="set this admin key's own code (admins only)"
    )
    p.add_argument("address")
    p.add_argument(
        "admin_code",
        help="6 characters, needs a lowercase, an uppercase and a digit 1-9",
    )

    p = sub.add_parser("delete-user", help="revoke a user permanently")
    p.add_argument("address")
    p.add_argument("admin_code")
    p.add_argument("name")

    p = sub.add_parser("disable-user", help="suspend a user without revoking it")
    p.add_argument("address")
    p.add_argument("admin_code")
    p.add_argument("name")

    p = sub.add_parser("enable-user", help="re-enable a suspended user")
    p.add_argument("address")
    p.add_argument("admin_code")
    p.add_argument("name")

    return {
        name: handle
        for name in (
            "list-users",
            "create-user",
            "set-admin-code",
            "delete-user",
            "disable-user",
            "enable-user",
        )
    }

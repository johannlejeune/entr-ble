from ..shared import VOLUME_CHOICES
from .common import handle


def register(sub):
    p = sub.add_parser(
        "change-admin-code", help="change the lock's admin code (admins and owners)"
    )
    p.add_argument("address")
    p.add_argument("old_code")
    p.add_argument("new_code")
    p.add_argument(
        "--name",
        help="lock name, only needed if never stored by set-owner/settings/enroll",
    )

    p = sub.add_parser("settings", help="volume, mute and auto-lock (owners)")
    p.add_argument("address")
    p.add_argument("admin_code")
    p.add_argument(
        "--volume",
        choices=VOLUME_CHOICES,
        help="high/medium/low/muted; a EURO only uses medium and muted",
    )
    p.add_argument("--auto-lock", choices=["on", "off"])
    p.add_argument(
        "--name",
        help="lock name, only needed if never stored by set-owner/settings/enroll",
    )

    return {
        name: handle
        for name in (
            "change-admin-code",
            "settings",
        )
    }

from .common import handle


def register(sub):
    p = sub.add_parser("unlock", help="unlock the door")
    p.add_argument("address")

    p = sub.add_parser("lock", help="lock the door")
    p.add_argument("address")

    return {
        name: handle
        for name in (
            "unlock",
            "lock",
        )
    }

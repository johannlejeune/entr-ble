def register(sub):
    p = sub.add_parser("unlock", help="unlock the door")
    p.add_argument("address")
    p.set_defaults(run=run)

    p = sub.add_parser("lock", help="lock the door")
    p.add_argument("address")
    p.set_defaults(run=run)


async def run(client, creds, args) -> list[str]:
    app_id = bytes.fromhex(creds.app_id)
    await getattr(client, args.command)(
        bytes.fromhex(creds.user_id), app_id, bytes.fromhex(creds.ble_ekey)
    )
    return [f"{args.command} sent"]

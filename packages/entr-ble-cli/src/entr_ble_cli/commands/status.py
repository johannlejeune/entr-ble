def register(sub):
    p = sub.add_parser("status", help="show lock, door and battery status")
    p.add_argument("address")
    p.add_argument(
        "--raw", action="store_true", help="also print the undecoded response bytes"
    )
    p.set_defaults(run=run)

    p = sub.add_parser("info", help="show serial number and firmware")
    p.add_argument("address")
    p.add_argument(
        "--raw", action="store_true", help="also print the undecoded response bytes"
    )
    p.set_defaults(run=run)

    p = sub.add_parser(
        "device-info", help="show model, device ID and firmware versions"
    )
    p.add_argument("address")
    p.add_argument(
        "--raw", action="store_true", help="also print the undecoded response bytes"
    )
    p.set_defaults(run=run)


async def run(client, creds, args) -> list[str]:
    method = {
        "status": client.get_device_config,
        "info": client.get_lock_sn,
        "device-info": client.get_device_info,
    }[args.command]
    fields = await method()
    lines = [
        f"{key}: {value}" for key, value in fields.items() if key != "raw" or args.raw
    ]
    if args.command == "info":
        lines.append(f"comm_version: {client.comm_version}")
    return lines

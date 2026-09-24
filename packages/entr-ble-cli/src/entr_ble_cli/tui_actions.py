from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    default: str = ""
    password: bool = False
    required: bool = True


@dataclass(frozen=True)
class Action:
    command: str
    label: str
    fields: tuple[Field, ...] = ()
    destructive: bool = False


SETUP_ACTIONS = (
    Action(
        "set-owner",
        "Set owner",
        (
            Field("admin_code", "New owner password", password=True),
            Field("name", "Lock name"),
            Field("user", "Owner name", "owner"),
            Field("provider", "Provider ID", "4"),
            Field("sync_time", "Sync time (yes/no)", "no"),
        ),
        True,
    ),
    Action(
        "enroll",
        "Claim owner slot",
        (
            Field("admin_code", "Owner password", password=True),
            Field("name", "Lock name (optional)", required=False),
        ),
        True,
    ),
    Action("activate", "Activate key", (Field("key_code", "Key code", password=True),)),
)

ACTION_GROUPS = (
    (
        "Access",
        (
            Action("unlock", "Unlock"),
            Action("lock", "Lock"),
        ),
    ),
    (
        "Users",
        (
            Action(
                "list-users",
                "List users",
                (Field("admin_code", "Admin code", password=True),),
            ),
            Action(
                "create-user",
                "Create user",
                (
                    Field("admin_code", "Admin code", password=True),
                    Field("name", "User name"),
                    Field("role", "Role", "user"),
                    Field("expiration", "Key expiry in hours", "3"),
                    Field("code", "Key code (optional)", required=False),
                ),
            ),
            Action(
                "set-admin-code",
                "Set own admin code",
                (Field("admin_code", "New admin code", password=True),),
            ),
            Action(
                "delete-user",
                "Delete user",
                (
                    Field("admin_code", "Admin code", password=True),
                    Field("name", "User name"),
                ),
                True,
            ),
            Action(
                "disable-user",
                "Disable user",
                (
                    Field("admin_code", "Admin code", password=True),
                    Field("name", "User name"),
                ),
                True,
            ),
            Action(
                "enable-user",
                "Enable user",
                (
                    Field("admin_code", "Admin code", password=True),
                    Field("name", "User name"),
                ),
            ),
        ),
    ),
    (
        "Settings",
        (
            Action(
                "change-admin-code",
                "Change admin code",
                (
                    Field("old_code", "Current admin code", password=True),
                    Field("new_code", "New admin code", password=True),
                    Field("name", "Lock name (optional)", required=False),
                ),
            ),
            Action(
                "settings",
                "Update settings",
                (
                    Field("admin_code", "Admin code", password=True),
                    Field("volume", "Volume: high, medium, low, muted", required=False),
                    Field("auto_lock", "Auto-lock: on, off", required=False),
                    Field("name", "Lock name (optional)", required=False),
                ),
            ),
        ),
    ),
    (
        "Information",
        (
            Action("status", "Status"),
            Action("info", "Lock information"),
            Action("device-info", "Device information"),
            Action(
                "get-errors",
                "Error log",
                (Field("query", "Query hex", "0000000000000000"),),
            ),
            Action(
                "audit-trail",
                "Audit trail",
                (Field("admin_code", "Admin code (optional)", required=False),),
            ),
        ),
    ),
    (
        "Maintenance",
        (
            Action(
                "calibrate",
                "Calibrate",
                (
                    Field("admin_code", "Admin code", password=True),
                    Field("door", "Door direction: left, right", "left"),
                    Field("type", "Lock type: normal, lift", "normal"),
                ),
            ),
            Action(
                "magnet-calibrate",
                "Calibrate door magnet",
                (Field("admin_code", "Admin code", password=True),),
            ),
            Action("set-time", "Set lock time"),
            Action(
                "factory-reset",
                "Factory reset",
                (Field("admin_code", "Admin code", password=True),),
                True,
            ),
        ),
    ),
)

ACTIONS = {action.command: action for _, group in ACTION_GROUPS for action in group}
ACTIONS.update({action.command: action for action in SETUP_ACTIONS})


def normalize_values(values: dict[str, str]) -> dict[str, object]:
    choices = {
        "role": {
            "user",
            "admin",
            "remote-control",
            "wall-reader",
            "integration-unit",
        },
        "volume": {"high", "medium", "low", "muted"},
        "auto_lock": {"on", "off"},
        "door": {"left", "right"},
        "type": {"normal", "lift"},
    }
    result: dict[str, object] = {}
    for key, value in values.items():
        if not value:
            continue
        if key == "provider" or key == "expiration":
            try:
                result[key] = int(value)
            except ValueError as exc:
                raise ValueError(
                    f"{key.replace('_', ' ').capitalize()} must be a whole number."
                ) from exc
        elif key == "sync_time":
            result[key] = _boolean_value(key, value)
        elif key in choices:
            if value not in choices[key]:
                valid = ", ".join(sorted(choices[key]))
                raise ValueError(
                    f"{key.replace('_', ' ').capitalize()} must be one of: {valid}."
                )
            result[key] = value
        else:
            result[key] = value
    return result


def _boolean_value(key: str, value: str) -> bool:
    if value.lower() in {"yes", "true", "1"}:
        return True
    if value.lower() in {"no", "false", "0"}:
        return False
    raise ValueError(f"{key.replace('_', ' ').capitalize()} must be yes or no.")

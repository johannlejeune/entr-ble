from uuid import UUID

REQUEST_SERVICE = UUID("c5e00100-d396-11e3-bb18-0002a5d5c51b")
REQUEST_CHAR_CONTROL = UUID("c5e00101-d396-11e3-bb18-0002a5d5c51b")
REQUEST_CHAR_PAYLOAD = UUID("c5e00102-d396-11e3-bb18-0002a5d5c51b")

RESPONSE_SERVICE = UUID("c5e00200-d396-11e3-bb18-0002a5d5c51b")
RESPONSE_CONTROL = UUID("c5e00201-d396-11e3-bb18-0002a5d5c51b")
RESPONSE_PRIMARY_PAYLOAD = UUID("c5e00202-d396-11e3-bb18-0002a5d5c51b")
RESPONSE_SECONDARY = UUID("c5e00203-d396-11e3-bb18-0002a5d5c51b")
RESPONSE_GENERAL_STATUS = UUID("c5e00204-d396-11e3-bb18-0002a5d5c51b")

# Dedicated FOTA service for device info, error logs and firmware updates.
FOTA_REQUEST_SERVICE = UUID("c5e00500-d396-11e3-bb18-0002a5d5c51b")
FOTA_REQUEST_CHAR_CONTROL = UUID("c5e00501-d396-11e3-bb18-0002a5d5c51b")
FOTA_REQUEST_CHAR_PAYLOAD = UUID("c5e00502-d396-11e3-bb18-0002a5d5c51b")
FOTA_RESPONSE_CONTROL = UUID("c5e00503-d396-11e3-bb18-0002a5d5c51b")
FOTA_RESPONSE_PAYLOAD = UUID("c5e00504-d396-11e3-bb18-0002a5d5c51b")

# Outer control-frame commands
CMD_SEND_PUBLIC_KEY = 10
CMD_HANDSHAKE1 = 11
CMD_SET_OWNER = 12
CMD_SET_OWNER_RESPONSE = 13
CMD_KDF = 14
CMD_CREATE_NEW_KEY = 15
CMD_GET_NEW_KEY = 16
CMD_UNLOCK = 17
CMD_LOCK = 18
CMD_OP_STATUS = 25
CMD_GET_KEYS = 26
CMD_GET_KEYS_RESPONSE = 27
CMD_REVOKE_KEY = 28
CMD_DISABLE_KEY = 29
CMD_ENABLE_KEY = 32
CMD_GET_DEVICE_CONFIG = 30
CMD_GET_DEVICE_CONFIG_RESPONSE = 31
CMD_SET_ADMIN_CODE = 36
CMD_RECOVER_OWNER = 38
CMD_GENERAL_ENCRYPTED = 120
CMD_GENERAL_PLAIN = 121
CMD_OP_SUCCESS_IMP = 100
CMD_OP_SUCCESS_EXP = 101
CMD_OP_ERROR = 102
# Acknowledgements the lock waits for before committing an operation.
CMD_SET_OWNER_ACK = 40
CMD_GET_NEW_KEY_ACK = 41
CMD_GET_DEVICE_CONFIG_RESPONSE_ACK = 42

CMD_GET_COMMUNICATION_VERSION = 43
CMD_GET_COMMUNICATION_VERSION_RESPONSE = 44
GET_SUPPORTED_COMM_VER = 70
GET_SUPPORTED_COMM_VER_RESPONSE = 71
GET_LOCK_SN = 72
GET_LOCK_SN_RESPONSE = 73

# Maintenance and settings commands.
CMD_GET_DEVICE_INFO = 45
CMD_GET_DEVICE_INFO_RESPONSE = 46
CMD_OP_DEVICE_CONFIG = 47
CMD_GET_ERRORS = 49
CMD_OP_LOCK_CALIB = 51
CMD_OP_MAGNET_CALIB = 52
CMD_OP_FACTORY_RESET = 53
CMD_UPDATE_TIME = 80
CMD_GET_DATA = 81
CMD_GET_DATA_RESPONSE = 82

# Firmware mode values returned with the lock serial number.
FIRMWARE_MODES = {
    0: "ENTR_EURO",
    1: "ENTR_DB",
    2: "ENTR_S",
    3: "ENTR_Tiny_Bridge",
    4: "ENTR_Universal_Bridge",
    7: "ENTR_HK",
}

CMD_KDF_RESPONSE = 20
CMD_GET_NEW_KEY_RESPONSE = 19
CMD_RECOVER_OWNER_RESPONSE = 39

ROLE_USER = 0
ROLE_ADMIN = 1
ROLE_OWNER = 2
ROLE_REMOTE_CONTROL = 3
ROLE_WALL_READER = 4
ROLE_INTEGRATION_UNIT = 5
ROLE_MOBILE = 6
ROLE_NAMES = {
    ROLE_USER: "user",
    ROLE_ADMIN: "admin",
    ROLE_OWNER: "owner",
    ROLE_REMOTE_CONTROL: "remote control",
    ROLE_WALL_READER: "wall reader",
    ROLE_INTEGRATION_UNIT: "integration unit",
    ROLE_MOBILE: "mobile",
}

# Manufacturer product id in BLE advertisements.
MANUFACTURER_PRODUCT_ID = 0xE7

LOCK_STATE_UNINITIALIZED = 0
LOCK_STATE_INITIALIZED = 1
LOCK_STATE_KEYS_PENDING = 2
LOCK_STATE_FAST_KEYS_PENDING = 3
LOCK_STATE_UNCALIBRATED = 4
LOCK_STATE_NAMES = {
    LOCK_STATE_UNINITIALIZED: "uninitialized",
    LOCK_STATE_INITIALIZED: "initialized",
    LOCK_STATE_KEYS_PENDING: "keys pending",
    LOCK_STATE_FAST_KEYS_PENDING: "fast keys pending",
    LOCK_STATE_UNCALIBRATED: "initialized, uncalibrated",
}

ADMIN_CODE_LENGTH = 6
KEY_CODE_LENGTH = 6
USER_ID_LENGTH = 16

# These values give the hours a key code remains redeemable, not the lifetime
# of the resulting key.
EXPIRATION_HOURS = (3, 6, 12, 24, 48, 72)

STATE_DISABLED = 0
STATE_ENABLED = 1
STATE_PENDING = 2
STATE_NAMES = {
    STATE_DISABLED: "disabled",
    STATE_ENABLED: "enabled",
    STATE_PENDING: "pending",
}

MODE_MANUAL = 1
MODE_AUTO = 0

# DEVICE_STATUS bitfield.
STATUS_BIT_AUTO_LOCK_OFF = 0x02
STATUS_BIT_MUTED = 0x04
STATUS_BIT_UNLOCKED = 0x08
STATUS_BIT_DOOR_OPEN = 0x10
STATUS_BIT_CHARGING = 0x20
STATUS_BIT_BATTERY_LOW = 0x40
STATUS_BIT_BATTERY_MED = 0x80

# Bits 0 and 2 form one volume field: 0 is loudest and 5 is muted. NIZ firmware
# exposes the full scale; EURO firmware commonly uses 1 and 5.
STATUS_VOLUME_MASK = 0x05
VOLUME_HIGH = 0
VOLUME_MEDIUM = 1
VOLUME_LOW = 4
VOLUME_MUTED = 5
VOLUME_NAMES = {0: "high", 1: "medium", 4: "low", 5: "muted"}

BATTERY_LOW = 0
BATTERY_MEDIUM = 1
BATTERY_HIGH = 2
BATTERY_NAMES = {BATTERY_LOW: "low", BATTERY_MEDIUM: "medium", BATTERY_HIGH: "high"}

# Offset added to the folded frame checksum.
CHECKSUM_OFFSET = 0xA0

# Try these encodings in order; the first round-tripping candidate supplies the
# sign byte at the start of the 16-byte lock name field.
LOCK_NAME_ENCODINGS = {
    69: "cp1250",  # E, Eastern Europe
    70: "cp1252",  # F, French
    72: "cp1255",  # H, Hebrew
    82: "cp1251",  # R, Russian
    67: "gb18030",  # C, Chinese
    84: "cp1254",  # T, Turkish
    65: "cp1256",  # A, Arabic
    76: "iso-8859-1",  # L, Latin
    94: "utf-8",  # ^
}
LOCK_NAME_MAX_BYTES = 12

# Audit trail event codes for NIZ firmware.
AUDIT_EVENTS = {
    1: "watchdog reset",
    2: "power-on reset",
    3: "software reset",
    16: "lock complete",
    17: "unlock complete",
    18: "lock error",
    19: "unlock error",
    20: "door opened",
    21: "door closed",
    22: "knob pressed",
    23: "knob released",
    24: "knob turned",
}

# Factory audit-trail code for NIZ locks.
DEFAULT_AUDIT_PASSWORD = "Aa1111"

# Two known GET_DEVICE_INFO update states; other values have an unknown outcome.
UPDATE_STATUS_NEVER_STARTED = bytes([0, 0, 0, 0])
UPDATE_STATUS_SUCCESS = bytes([48, 255, 0, 0])

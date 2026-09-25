from homeassistant.const import Platform

DOMAIN = "entr_ble"
PLATFORMS = [Platform.LOCK, Platform.BUTTON, Platform.SENSOR]

CONF_ADDRESS = "address"
CONF_APP_ID = "app_id"
CONF_USER_ID = "user_id"
CONF_BLE_EKEY = "ble_ekey"
CONF_KDF_ID = "kdf_id"
CONF_AES_KEY = "aes_key"
CONF_COMM_VERSION = "comm_version"
CONF_ROLE = "role"
CONF_LOCK_NAME = "lock_name"

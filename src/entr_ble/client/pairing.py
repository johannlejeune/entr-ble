from typing import TypedDict

import entr_ble.const as const
import entr_ble.crypto as crypto

from ..session_crypto import SessionCrypto
from .fields import StatusData, decode_status, fixed_length
from .transport import EntrProtocolError, TransportClient


class OwnerCredentials(TypedDict):
    ble_ekey: bytes
    kdf_id: int
    user_id: bytes


class OwnerSetup(TypedDict):
    ble_ekey: bytes
    kdf_id: int
    status: StatusData


class NewKeyCredentials(TypedDict):
    ble_ekey: bytes
    role: int
    provider_id: int
    user_id: bytes
    kdf_id: int


class Pairing(TransportClient):
    async def fetch_comm_version(self) -> str:
        # The payload byte is an unused placeholder; the command id is in the
        # outer control frame.
        _, payload = await self._send_raw(
            const.CMD_GET_COMMUNICATION_VERSION, bytes([0])
        )
        length = payload[1]
        self.comm_version = payload[2 : 2 + length].decode("ascii")
        return self.comm_version

    async def pair(self) -> None:
        """One-time ECDH key exchange. Only valid the very first time this
        client's key pair talks to a given lock; save the resulting credentials
        for later sessions.
        """
        our_pub = crypto.public_key_bytes(self.private_key)
        _, response = await self._send_raw(const.CMD_SEND_PUBLIC_KEY, our_pub)
        remote_aes_pub = response[0:64]
        remote_iv = response[128:144]
        key = crypto.derive_session_key(self.private_key, remote_aes_pub)
        self.session = SessionCrypto(key)
        self.session.set_iv(remote_iv)

    async def handshake(self, app_id: bytes) -> None:
        await self._send_encrypted(const.CMD_HANDSHAKE1, app_id)

    async def recover_owner(self, admin_code: str, app_id: bytes) -> OwnerCredentials:
        fields = admin_code.encode("ascii") + app_id
        response = await self._send_encrypted(const.CMD_RECOVER_OWNER, fields)
        if response is None:
            raise EntrProtocolError("no encrypted response to RECOVER_OWNER")
        # response[0] echoes the inner response command byte; fields start at 1.
        ble_ekey = response[1:33]
        kdf_id = response[33]
        user_id = response[34:50]
        return {"ble_ekey": ble_ekey, "kdf_id": kdf_id, "user_id": user_id}

    async def set_owner(
        self,
        admin_code: str,
        app_id: bytes,
        user_id: bytes,
        lock_name: bytes,
        provider_id: int,
    ) -> OwnerSetup:
        """Claims an uninitialized lock.

        prev_admin_code is the factory placeholder 000000; the response carries
        the same credentials as RecoverOwner and requires SET_OWNER_ACK.
        """
        fields = (
            b"000000"
            + fixed_length(admin_code, const.ADMIN_CODE_LENGTH, "admin code")
            + app_id
            + user_id
            + bytes([const.MODE_AUTO])
            + lock_name
            + bytes([provider_id])
        )
        outer_command, response = await self._exchange_encrypted(
            const.CMD_SET_OWNER, fields
        )
        if outer_command != const.CMD_GENERAL_ENCRYPTED or response is None:
            raise EntrProtocolError("no encrypted response to SET_OWNER")
        await self._send_ack(const.CMD_SET_OWNER_ACK)
        # The response carries ekey(32), kdf id, status, then battery percentage
        # past comm version 1.28r1; it has no passcode field.
        return {
            "ble_ekey": response[1:33],
            "kdf_id": response[33],
            "status": decode_status(
                response[34], response[35] if len(response) > 35 else None, None
            ),
        }

    async def get_new_key(self, key_code: str, app_id: bytes) -> NewKeyCredentials:
        """Redeems a pending key created by an owner or admin, so this device
        gets its own credentials without touching theirs. The request uses role
        6 as a placeholder; the assigned role comes back in the response.
        """
        fields = (
            fixed_length(key_code, const.KEY_CODE_LENGTH, "key code")
            + app_id
            + bytes([6])
        )
        response = await self._send_encrypted(const.CMD_GET_NEW_KEY, fields)
        if response is None:
            raise EntrProtocolError("no encrypted response to GET_NEW_KEY")
        await self._send_ack(const.CMD_GET_NEW_KEY_ACK)
        # Note the field order differs from RecoverOwner's response.
        return {
            "ble_ekey": response[1:33],
            "role": response[33],
            "provider_id": response[34],
            "user_id": response[35:51],
            "kdf_id": response[51],
        }

    async def kdf_resync(self, kdf_id: int, role: int, key: bytes) -> StatusData | None:
        """Re-derives the session IV, and picks up the status the lock piggybacks
        on the response, which saves a separate GetDeviceConfig round trip."""
        self.session = SessionCrypto(key)
        _, payload = await self._send_raw(const.CMD_KDF, bytes([kdf_id, role]))
        iv = payload[1:17]
        self.session.set_iv(iv)
        # [0] command echo, [1:17] IV, [17:89] signature, then the status byte;
        # the battery/passcode bytes only exist past comm version 1.28r1.
        if len(payload) > 89:
            self.status_raw = payload[89]
            self.status = decode_status(
                payload[89],
                payload[90] if len(payload) > 90 else None,
                payload[91] if len(payload) > 91 else None,
            )
        return self.status

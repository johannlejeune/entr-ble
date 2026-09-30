from typing import TypedDict

import entr_ble.const as const
import entr_ble.crypto as crypto

from ..session_crypto import SessionCrypto
from .fields import StatusData, decode_status, fixed_bytes, fixed_length
from .transport import EntrProtocolError, TransportClient, validate_response


class OwnerCredentials(TypedDict):
    """Recovered owner credentials: 32-byte lock key, KDF identifier and 16-byte user
    identifier.
    """

    ble_ekey: bytes
    kdf_id: int
    user_id: bytes


class OwnerSetup(TypedDict):
    """New owner credentials and decoded status; the user identifier is supplied to
    set_owner().
    """

    ble_ekey: bytes
    kdf_id: int
    status: StatusData


class NewKeyCredentials(TypedDict):
    """Redeemed credentials: 32-byte lock key, assigned role, provider identifier,
    16-byte user identifier and KDF identifier.
    """

    ble_ekey: bytes
    role: int
    provider_id: int
    user_id: bytes
    kdf_id: int


class Pairing(TransportClient):
    """Provision credentials or restore an encrypted session on a connected lock."""

    async def fetch_comm_version(self) -> str:
        """GET_COMMUNICATION_VERSION (43): read and cache the lock's ASCII communication
        version.

        Requires a connection, but no encrypted session. Returns the version string and
        sets comm_version; malformed or non-ASCII responses raise EntrProtocolError.
        """
        # The payload byte is an unused placeholder; the command id is in the
        # outer control frame.
        _, payload = await self._send_raw(
            const.CMD_GET_COMMUNICATION_VERSION, bytes([0])
        )
        validate_response(payload, const.CMD_GET_COMMUNICATION_VERSION_RESPONSE, 2)
        length = payload[1]
        if len(payload) < 2 + length:
            raise EntrProtocolError("truncated communication version")
        try:
            self.comm_version = payload[2 : 2 + length].decode("ascii")
        except UnicodeDecodeError as exc:
            raise EntrProtocolError("invalid communication version") from exc
        return self.comm_version

    async def pair(self) -> None:
        """SEND_PUBLIC_KEY (10): establish an encrypted session for provisioning new
        credentials.

        Requires a connection. Sets session from the public-key exchange and returns
        None; malformed public-key responses raise EntrProtocolError. Follow with
        handshake() and one provisioning operation, then retain session.key and the
        returned credentials for kdf_resync() on later connections.
        """
        our_pub = crypto.public_key_bytes(self.private_key)
        _, response = await self._send_raw(const.CMD_SEND_PUBLIC_KEY, our_pub)
        if len(response) < 144:
            raise EntrProtocolError("truncated public key response")
        remote_aes_pub = response[0:64]
        remote_iv = response[128:144]
        try:
            key = crypto.derive_session_key(self.private_key, remote_aes_pub)
        except ValueError as exc:
            raise EntrProtocolError("invalid lock public key") from exc
        self.session = SessionCrypto(key)
        self.session.set_iv(remote_iv)

    async def handshake(self, app_id: bytes) -> None:
        """HANDSHAKE1 (11): send the 16-byte application identifier before provisioning.

        Requires a connection and the session established by pair(). Reuse this app_id
        for provisioning and subsequent access commands. Returns None without validating
        a success echo; an invalid identifier length raises ValueError.
        """
        await self._send_encrypted(
            const.CMD_HANDSHAKE1, fixed_bytes(app_id, 16, "application id")
        )

    async def recover_owner(self, admin_code: str, app_id: bytes) -> OwnerCredentials:
        """RECOVER_OWNER (38): replace the initialized lock's current owner credentials.

        Requires pair() and handshake(app_id). Supply the six-character ASCII owner
        admin code and the same 16-byte app_id. Returns the new 32-byte ble_ekey, kdf_id
        and 16-byte user_id; retain these together with app_id and session.key. The
        previous owner credential loses access. Invalid field lengths raise ValueError,
        non-ASCII codes raise UnicodeEncodeError and malformed responses raise
        EntrProtocolError.
        """
        fields = fixed_length(
            admin_code, const.ADMIN_CODE_LENGTH, "admin code"
        ) + fixed_bytes(app_id, 16, "application id")
        response = await self._send_encrypted(const.CMD_RECOVER_OWNER, fields)
        validate_response(response, const.CMD_RECOVER_OWNER_RESPONSE, 50)
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
        """SET_OWNER (12): claim an uninitialized lock and acknowledge the resulting
        credentials.

        Requires pair() and handshake(app_id). Supply a six-character ASCII admin code,
        16-byte app_id and user_id, a 16-byte lock_name from build_lock_name(), and a
        one-byte provider_id. Initializes automatic mode and returns the 32-byte
        ble_ekey, kdf_id and decoded status after sending SET_OWNER_ACK (40). Retain the
        supplied identifiers and session.key with the returned credentials. Invalid
        field lengths or provider_id raise ValueError, non-ASCII codes raise
        UnicodeEncodeError and malformed responses raise EntrProtocolError.
        """
        fields = (
            b"000000"
            + fixed_length(admin_code, const.ADMIN_CODE_LENGTH, "admin code")
            + fixed_bytes(app_id, 16, "application id")
            + fixed_bytes(user_id, 16, "user id")
            + bytes([const.MODE_AUTO])
            + fixed_bytes(lock_name, 16, "lock name")
            + bytes([provider_id])
        )
        outer_command, response = await self._exchange_encrypted(
            const.CMD_SET_OWNER, fields
        )
        if outer_command != const.CMD_GENERAL_ENCRYPTED or response is None:
            raise EntrProtocolError("no encrypted response to SET_OWNER")
        validate_response(response, const.CMD_SET_OWNER_RESPONSE, 35)
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
        """GET_NEW_KEY (16): redeem a pending key created by an owner or admin.

        Requires pair() and handshake(app_id). Supply the six-character ASCII key code
        and the same 16-byte app_id before the pending key expires. Returns ble_ekey (32
        bytes), the assigned role, provider_id, user_id (16 bytes) and kdf_id after
        sending GET_NEW_KEY_ACK (41) to complete activation. Retain these with app_id
        and session.key; existing users keep their credentials. Invalid field lengths
        raise ValueError, non-ASCII codes raise UnicodeEncodeError and malformed
        responses raise EntrProtocolError.
        """
        fields = (
            fixed_length(key_code, const.KEY_CODE_LENGTH, "key code")
            + fixed_bytes(app_id, 16, "application id")
            + bytes([6])
        )
        response = await self._send_encrypted(const.CMD_GET_NEW_KEY, fields)
        validate_response(response, const.CMD_GET_NEW_KEY_RESPONSE, 52)
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
        """KDF (14): restore an encrypted session using saved credentials and the lock's
        fresh IV.

        Requires a connection, but no existing session. Supply the saved one-byte
        kdf_id, assigned one-byte role and 16-byte AES session key, rather than the
        32-byte ble_ekey. Replaces session and caches status and status_raw; returns
        decoded status when included by the lock, otherwise None. Invalid key length or
        byte values raise ValueError and malformed responses raise EntrProtocolError.
        The returned signature is not verified by this client.
        """
        session = SessionCrypto(key)
        _, payload = await self._send_raw(const.CMD_KDF, bytes([kdf_id, role]))
        validate_response(payload, const.CMD_KDF_RESPONSE, 89)
        iv = payload[1:17]
        session.set_iv(iv)
        self.session = session
        self.status = None
        self.status_raw = None
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

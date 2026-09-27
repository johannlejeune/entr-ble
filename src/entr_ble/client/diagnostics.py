import re
from typing import NotRequired, TypedDict

import entr_ble.const as const

from .fields import AuditRecord, fixed_bytes, fixed_length, parse_audit_record
from .transport import EntrProtocolError, TransportClient, validate_response


class DeviceInfo(TypedDict):
    device_id: str
    model: str
    code_version: str
    update_status: str
    raw: str
    version_ble: NotRequired[str]
    version_mcu: NotRequired[str]
    version_radio: NotRequired[str]
    version_bootloader: NotRequired[str]


class ErrorLog(TypedDict):
    response_code: int
    length: int
    empty: bool
    data: str
    raw: str


class AuditTrailStatus(TypedDict):
    type: int
    records_count: int | None


class Diagnostics(TransportClient):
    async def get_device_info(self) -> DeviceInfo:
        """GET_DEVICE_INFO (45): model, device id and BLE/MCU/radio firmware
        versions as length-prefixed strings, plus a 4-byte update status.

        Uses the FOTA GATT service. Direct session crypto needs comm version
        1.29r3+; older locks require a separate FOTA IV exchange.
        """
        version = re.fullmatch(r"(\d+)\.(\d+)r(\d+)", self.comm_version)
        if version is None or tuple(map(int, version.groups())) < (1, 29, 3):
            raise EntrProtocolError(
                f"GET_DEVICE_INFO needs comm version 1.29r3+, this lock reports {self.comm_version!r}"
            )
        self._require_fota()
        outer_command, payload = await self._exchange_encrypted_on(
            const.CMD_GET_DEVICE_INFO, b"", fota=True
        )
        if outer_command != const.CMD_GENERAL_ENCRYPTED or payload is None:
            raise EntrProtocolError("no encrypted response to GET_DEVICE_INFO")
        validate_response(payload, const.CMD_GET_DEVICE_INFO_RESPONSE, 1)

        def _raw_string(offset: int) -> tuple[bytes, int]:
            # Each string has a length prefix; offset 0 is the command echo.
            if offset >= len(payload):
                raise EntrProtocolError("missing device information field")
            length = payload[offset]
            if offset + 1 + length > len(payload):
                raise EntrProtocolError("truncated device information field")
            return payload[offset + 1 : offset + 1 + length], offset + 1 + length

        device_id, offset = _raw_string(1)
        model_raw, offset = _raw_string(offset)
        code_version_raw, offset = _raw_string(offset)
        update_status = payload[offset : offset + 4]
        if len(update_status) != 4:
            raise EntrProtocolError("truncated firmware update status")

        def _text(raw: bytes) -> str:
            # Version fields may be NUL padded.
            return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")

        code_version = _text(code_version_raw)
        # Two four-byte values identify known update states.
        if update_status == const.UPDATE_STATUS_SUCCESS:
            status_label = "last firmware install successful"
        elif update_status == const.UPDATE_STATUS_NEVER_STARTED:
            status_label = "no firmware update ever started"
        else:
            status_label = "firmware update started, outcome not confirmed"
        info: DeviceInfo = {
            "device_id": device_id.hex(),
            "model": _text(model_raw),
            "code_version": code_version,
            "update_status": f"{status_label} ({' '.join(str(b) for b in update_status)})",
            "raw": payload.hex(),
        }
        # Version segments use B<ble>M<mcu>N<radio>F<...>.
        parts = re.split(r"[BMNF]", code_version)
        if len(parts) >= 4:
            info["version_ble"], info["version_mcu"], info["version_radio"] = (
                parts[1],
                parts[2],
                parts[3],
            )
        boot_parts = re.split(r"[HDL]", info["model"])
        if len(boot_parts) >= 4:
            info["version_bootloader"] = boot_parts[3]
        return info

    async def get_errors(self, query: bytes) -> ErrorLog:
        """GET_ERRORS (49): the firmware fault log, on the FOTA service only
        (the main service answers UnsupportedCmdInBuff).

        The meaning of the 8-byte query is unknown. An ENTR EURO (comm 1.29r5)
        returns the same dump regardless of its content. The response uses
        `[response code][length][data]` and reports code 8. Command-level
        errors (OP_ERROR) do not show up in the log.
        """
        self._require_fota()
        fields = fixed_bytes(query, 8, "error query")
        outer_command, payload = await self._exchange_encrypted_on(
            const.CMD_GET_ERRORS, fields, fota=True
        )
        if (
            outer_command != const.CMD_GENERAL_ENCRYPTED
            or payload is None
            or len(payload) < 2
        ):
            raise EntrProtocolError("no encrypted response to GET_ERRORS")
        length = payload[1]
        if len(payload) < 2 + length:
            raise EntrProtocolError("truncated error log")
        data = payload[2 : 2 + length]
        return {
            "response_code": payload[0],
            "length": length,
            "empty": not any(data),
            "data": data.hex(),
            "raw": payload.hex(),
        }

    async def audit_trail_status(
        self, admin_code: str, app_id: bytes
    ) -> AuditTrailStatus:
        """GET_DATA (81) with type 3: how many records the log holds. NIZ only."""
        fields = (
            fixed_length(admin_code, const.ADMIN_CODE_LENGTH, "admin code")
            + fixed_bytes(app_id, 16, "application id")
            + bytes([3, 0])
        )
        payload = await self._get_data_response(fields)
        data = payload[3 : 3 + payload[2]]
        return {"type": payload[1], "records_count": data[0] if data else None}

    async def audit_trail_records(
        self, admin_code: str, app_id: bytes, batch_size: int = 50
    ) -> list[AuditRecord]:
        """GET_DATA (81) with type 1: reads event records.

        The lock streams one record per response frame without being asked
        again, mirroring GetKeys; a trailing tag of 0xFF marks the end.
        """
        fields = (
            fixed_length(admin_code, const.ADMIN_CODE_LENGTH, "admin code")
            + fixed_bytes(app_id, 16, "application id")
            + bytes([1, 1, batch_size])
        )
        records: list[AuditRecord] = []
        payload = await self._get_data_response(fields)
        while True:
            validate_response(payload, const.CMD_GET_DATA_RESPONSE, 3)
            length = payload[2]
            if len(payload) < 3 + length + 1:
                raise EntrProtocolError("truncated audit trail record")
            try:
                records.append(parse_audit_record(payload[3 : 3 + length]))
            except ValueError as exc:
                raise EntrProtocolError("invalid audit trail record") from exc
            # The LAST_T flag byte sits right after the record data.
            if payload[3 + length] == 0xFF:
                return records
            if len(records) >= 10000:
                raise EntrProtocolError("audit trail stream exceeds record limit")
            payload = await self._receive_encrypted()
            if not payload or payload[0] != const.CMD_GET_DATA_RESPONSE:
                raise EntrProtocolError("audit trail stream ended unexpectedly")

    def _require_fota(self) -> None:
        if not self.fota_available:
            raise EntrProtocolError(
                "this lock does not expose the FOTA service (c5e00500-...)"
            )

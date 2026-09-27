import unittest
from dataclasses import replace

from entr_ble.crypto import derive_session_key, generate_keypair, public_key_bytes
from entr_ble.framing import (
    ChunkAssembler,
    build_control_frame,
    build_payload_chunks,
    parse_control_frame,
)
from entr_ble.session_crypto import SessionCrypto


class FramingTests(unittest.TestCase):
    def test_serial_request_wire_format(self):
        expected = bytes.fromhex("48000100a08900")
        self.assertEqual(build_control_frame(72, b"\x00"), expected)
        response = parse_control_frame(expected)
        self.assertEqual((response.command, response.payload), (72, b"\x00"))

    def test_inline_and_chunked_round_trip(self):
        for size in (0, 1, 14, 15, 18, 19, 144, 1024):
            with self.subTest(size=size):
                payload = bytes(i % 256 for i in range(size))
                frame = parse_control_frame(build_control_frame(120, payload))
                self.assertEqual(frame.payload_length, size)
                if size <= 14:
                    self.assertEqual(frame.payload or b"", payload)
                else:
                    assembler = ChunkAssembler()
                    assembler.reset(frame.payload_checksum, size)
                    chunks = build_payload_chunks(payload)
                    for chunk in chunks[:-1]:
                        self.assertIsNone(assembler.feed(chunk))
                    self.assertEqual(assembler.feed(chunks[-1]), payload)

    def test_malformed_control_frames(self):
        valid = build_control_frame(120, b"abc")
        for frame in (b"", valid[:5], valid[:-1], valid[:5] + b"\x00" + valid[6:]):
            with self.subTest(frame=frame), self.assertRaises(ValueError):
                parse_control_frame(frame)
        with self.assertRaises(ValueError):
            parse_control_frame(valid[:-1] + b"d")

    def test_bad_chunks_fail_without_accepting_partial_payload(self):
        payload = bytes(range(36))
        frame = parse_control_frame(build_control_frame(120, payload))
        for chunk in (
            b"",
            b"\x01",
            b"\x01\x00",
            b"\x01\x13",
            b"\x01\x12a",
            b"\x02\x01a",
        ):
            with self.subTest(chunk=chunk), self.assertRaises(ValueError):
                assembler = ChunkAssembler(frame.payload_checksum)
                assembler.feed(chunk)
        for response in (
            replace(frame, payload_length=35),
            replace(frame, payload_checksum=0),
        ):
            assembler = ChunkAssembler()
            assembler.reset(response.payload_checksum, response.payload_length)
            with self.assertRaises(ValueError):
                for chunk in build_payload_chunks(payload):
                    assembler.feed(chunk)

    def test_outbound_frame_limits(self):
        for command, payload in ((256, b""), (-1, b""), (1, bytes(65536))):
            with self.subTest(command=command), self.assertRaises(ValueError):
                build_control_frame(command, payload)


class CryptoTests(unittest.TestCase):
    def test_peer_sessions_derive_the_same_key(self):
        first, second = generate_keypair(), generate_keypair()
        key = derive_session_key(first, public_key_bytes(second))
        self.assertEqual(key, derive_session_key(second, public_key_bytes(first)))
        sender, receiver = SessionCrypto(key), SessionCrypto(key)
        for session in (sender, receiver):
            session.set_iv(bytes(range(16)))
        for plaintext in (b"", b"unlock", bytes(range(255))):
            self.assertEqual(receiver.decrypt(sender.encrypt(plaintext)), plaintext)
        with self.assertRaises(ValueError):
            derive_session_key(first, public_key_bytes(second) + b"extra")

    def test_invalid_session_material_and_ciphertext(self):
        with self.assertRaises(ValueError):
            SessionCrypto(bytes(32))
        session = SessionCrypto(bytes(16))
        with self.assertRaises(ValueError):
            session.set_iv(bytes(15))
        for wire in (b"", b"\x01", bytes(16), bytes(18)):
            with self.subTest(wire=wire), self.assertRaises(ValueError):
                session.decrypt(wire)

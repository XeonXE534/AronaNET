# Test written by ChatGPT cuz I cant be arsed.
# Yeah, yeah vide-coding tests is bad
# But I don't use pytest much for testing, only for basic stuff
# So it's fine...probably

import pytest
from src.aronanet.protocol.messages import Message, MessageType
import zlib

def test_message_pack_basic():
    msg = Message(msg_type=MessageType.TEXT, payload=b"hello")
    packed = msg.pack()

    assert isinstance(packed, bytes)
    assert packed[0] == msg.version
    assert packed[1] == MessageType.TEXT

    length_field = int.from_bytes(packed[2:6], "big")
    # body = nonce + encrypted payload
    body_len = len(packed) - 8 - 4  # remove header(8) + checksum(4)
    assert length_field == body_len

    # last 4 bytes are checksum
    checksum_recv = int.from_bytes(packed[-4:], 'big')
    assert checksum_recv == zlib.crc32(packed[:-4])

def test_message_unpack_roundtrip():
    """Message.pack() and Message.unpack() should return same message."""
    payload = b"Lore ipsum but worse"
    msg = Message(msg_type=MessageType.SUP, payload=payload)

    packed = msg.pack()
    unpacked = Message.unpack(packed)

    assert unpacked.version == msg.version
    assert unpacked.msg_type == msg.msg_type
    assert unpacked.payload == payload
    assert unpacked.msg_id == msg.msg_id


def test_checksum_validation():
    """Corrupted packet must raise error."""
    msg = Message(msg_type=MessageType.TEXT, payload=b"yo")
    packed = bytearray(msg.pack())

    # corrupt payload byte
    packed[8] ^= 0xFF

    with pytest.raises(ValueError):
        Message.unpack(bytes(packed))


def test_msg_id_auto_increment():
    """Message IDs should increment and wrap at 65536."""
    msg1 = Message(payload=b"a")
    msg2 = Message(payload=b"b")

    assert msg2.msg_id == (msg1.msg_id + 1) % 65536


def test_unpack_rejects_short_data():
    """Too-small packets must fail instantly."""
    with pytest.raises(ValueError):
        Message.unpack(b"\x01\x10")  # way too short


def test_unpack_length_mismatch():
    """Faked length field should be caught by unpack slicing."""
    msg = Message(msg_type=MessageType.TEXT, payload=b"aaa")
    packed = bytearray(msg.pack())

    # Fake a bigger length than actual payload
    packed[2:6] = (9999).to_bytes(4, "big")

    # unpack should either error on slicing or checksum mismatch
    with pytest.raises(Exception):
        Message.unpack(bytes(packed))

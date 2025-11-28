from enum import IntEnum
from dataclasses import dataclass, field
from threading import Lock
from typing import ClassVar
import zlib

from ..utils.logger import get_logger
from .crypto import encrypt, decrypt

class MessageType(IntEnum):
    """Protocol defining"""
    HI = 0x01
    AUTH = 0x02
    AUTH_OK = 0x03
    AUTH_FAIL = 0x04
    TEXT = 0x10
    IMAGE = 0x11
    TYPING = 0x12
    ONLINE = 0x20
    OFFLINE = 0x21
    SUP = 0x30
    ADIOS = 0x31
    SHIT = 0xFF

@dataclass
class Message:
    """Does shit related to messages"""
    version: int = 1
    msg_type: MessageType = MessageType.TEXT
    payload: bytes = b''
    msg_id: int = field(default=None, init=False)

    _counter: ClassVar[int] = 0
    _lock: ClassVar[Lock] = Lock()

    logger = get_logger("ProtocolControl")

    def __post_init__(self):
        if self.msg_id is None:
            with Message._lock:
                self.msg_id = Message._counter
                Message._counter = (Message._counter +1) % 65536

    def pack(self):
        """Pack message"""
        nonce, enc_payload = encrypt(self.payload)
        body = nonce + enc_payload
        length = len(body)
        header = (
                bytes([self.version, self.msg_type]) +
                length.to_bytes(4, "big") +
                self.msg_id.to_bytes(2, "big")
        )
        checksum = zlib.crc32(header + body).to_bytes(4, "big")

        self.logger.debug(f"Packing msg_id: {self.msg_id}, type: {self.msg_type.name}, length: {length} :)")
        return header + body + checksum

    @classmethod
    def unpack(cls, data: bytes):
        """Unpack message"""
        version = data[0]
        msg_type = MessageType(data[1])
        length = int.from_bytes(data[2:6], "big")
        msg_id = int.from_bytes(data[6:8], "big")

        if len(data) < 8 + length + 4:
            cls.logger.error(f"Data too short message :/")
            raise ValueError("Data too short message")

        body = data[8:8 + length]
        nonce = body[:12]
        ciphertext = body[12:]

        checksum_recv = int.from_bytes(data[8 + length:12 + length], "big")
        checksum_calc = zlib.crc32(data[0:8] + body)
        if checksum_calc != checksum_recv:
            raise ValueError("Checksum mismatch :(")

        payload = decrypt(nonce, ciphertext)

        cls.logger.debug(f"Unpacked msg_id: {msg_id}, type: {msg_type.name} :)")
        msg = cls(version=version, msg_type=msg_type, payload=payload)
        msg.msg_id = msg_id
        return msg
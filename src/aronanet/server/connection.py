import asyncio
from typing import Optional

from ..protocol.messages import Message, MessageType
from ..protocol.crypto import SecureChannel, KeyExchange
from ..utils.logger import get_logger

logger = get_logger("Connection")

class ClientConnection:
    """Represents one client connection with encryption state"""
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader =reader
        self.writer = writer
        self.user = writer.get_extra_info("peername")

        self.username : Optional[str] = None
        self.authenticated = False
        self.channel: Optional[str] = None

        self.secure_channel = SecureChannel()
        self.key_exchange = KeyExchange()

        logger.info(f"New connection object for {self.user}")

    async def do_handshake(self) -> bool:
        """Perform key exchange handshake"""
        try:
            logger.debug(f"Waiting for HI from {self.user}")
            msg = await self.read_msg(encrypted=False)

            if msg.msg_type != MessageType.HI:
                logger.warning(f"Expected HI, got {msg.msg_type.name} from {self.addr}")
                return False

            if len(msg.payload) != 32:
                logger.error(f"Invalid pubkey length from {self.addr}")
                return False

            client_pubkey = msg.payload
            shared_key = self.key_exchange.derive_shared_key(client_pubkey)
            self.secure_channel.setup_shared_key(shared_key)

            logger.info(f"Key exchange complete with {self.user} :)")

            server_pubkey = self.key_exchange.get_public_bytes()
            reply = Message(msg_type=MessageType.HI, payload=server_pubkey)
            await self.send_msg(reply, encrypted=False)

            return True

        except Exception as e:
            logger.error(f"Handshake failed with {self.user}: {e}")
            return False

    async def read_msg(self, encrypted=True) -> Message:
        """Read one message from connection"""
        length_bytes = await self.reader.readexactly(4)
        pack_len = int.from_bytes(length_bytes, "big")

        pack = await self.reader.readexactly(pack_len)

        channel = self.secure_channel if encrypted else None
        msg = Message.unpack(pack, secure_channel=channel)

        return  msg

    async def send_msg(self, msg: Message, encrypted= True):
        """Send one message to connection"""
        channel  = self.secure_channel if encrypted else None
        packed = msg.pack(secure_channel=channel)

        self.writer.write(len(packed).to_bytes(4, "big") + packed)
        await self.writer.drain()

    def close(self):
        """Close connection"""
        try:
            self.writer.close()
        except Exception as e:
            logger.warning(f"Failed to close connection: {e}")
            pass
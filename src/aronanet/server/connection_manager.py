from typing import  Dict, Set, Optional, List

from .connection import ClientConnection
from ..protocol.messages import Message
from ..utils.logger import get_logger

logger = get_logger("ConnectionManager")

class ConnectionManager:
    """Manages all active connections and routing"""
    def __init__(self):
        self.connections: Dict[str, ClientConnection] = {}
        self.channels: Dict[str, Set[str]] = {"general": set()}
        self.user_channels: Dict[str, str] = {}

        logger.info("ConnectionManager initialized")

    def add_user(self, username: str, conn: ClientConnection):
        """Add authenticated user"""
        if username in self.connections:
            logger.warning(f"User {username} already connected, kicking old session")
            old_conn = self.connections[username]
            old_conn.close()

        self.connections[username] = conn
        self.join_channel(username, "general")
        conn.channel = "general"

        logger.info(f"{username} added to connection pool :)")

    def remove_user(self, username: str):
        """Remove disconnected user"""
        if username in self.connections:
            if username in self.user_channels:
                channel = self.user_channels[username]
                self.leave_channel(username, channel)

            del self.connections[username]
            logger.info(f"{username} removed from pool :3")

    def get_connection(self, username: str) -> Optional[ClientConnection]:
        """Get connection for user"""
        return self.connections.get(username)

    def join_channel(self, username: str, channel: str):
        """User joins a channel"""
        if username in self.user_channels:
            self.leave_channel(username, self.user_channels[username])

        if channel not in self.channels:
            self.channels[channel] = set()
            logger.info(f"Created new channel #{channel} :3")

        self.channels[channel].add(username)
        self.user_channels[username] = channel

        conn = self.get_connection(username)
        if conn:
            conn.channel = channel

        logger.info(f"{username} joined #{channel} :)")

    def leave_channel(self, username: str, channel: str):
        """User leaves a channel"""
        if channel in self.channels:
            self.channels[channel].discard(username)

        if not self.channels[channel] and channel != "general":
            del self.channels[channel]
            logger.info(f"Deleted empty channel #{channel} >:3")

        if username in self.user_channels:
            del self.user_channels[username]

        logger.info(f"{username} left #{channel} :3")

    async def scream_to_channel(self, channel: str, msg: Message, exclude: Optional[str] = None):
        """Send message to everyone in channel"""
        if channel not in self.channels:
            logger.warning(f"Tried to broadcast to non-existent channel #{channel} :/")
            return

        sent_count = 0
        for username in self.channels[channel]:
            if username == exclude:
                continue

            conn = self.get_connection(username)
            if conn:
                try:
                    await conn.send_msg(msg)
                    sent_count += 1

                except Exception as e:
                    logger.error(f"Failed to send to {username}: {e} :(")

        logger.debug(f"Broadcast to #{channel}: {sent_count} users :3")

    async def scream_to_user(self, username: str, msg: Message) -> bool:
        """Send direct message to specific user"""
        conn = self.get_connection(username)
        if not conn:
            logger.warning(f"User {username} not connected")
            return False

        try:
            await conn.send_msg(msg)
            return True

        except Exception as e:
            logger.error(f"Failed to send DM to {username}: {e}")
            return False

    def get_channel_users(self, channel: str) -> List[str]:
        """Get list of users in channel"""
        if channel not in self.channels:
            return []
        return list(self.channels[channel])

    def get_all_users(self) -> List[str]:
        """Get all connected users"""
        return list(self.connections.keys())

    def get_user_channel(self, username: str) -> Optional[str]:
        """Get which channel user is in"""
        return self.user_channels.get(username)
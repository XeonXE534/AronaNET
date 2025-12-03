import asyncio
from rich.console import Console
from typing import Dict

from ..utils.logger import get_logger
from ..utils.config import AronaSettings
from ..protocol.messages import Message, MessageType
from .connection_manager import ConnectionManager
from .connection import ClientConnection
from .bore_manager import BoreManager

console = Console()
logger = get_logger("AronaServer")

class AronaServer:
    """Async raw TCP server for AoNET"""
    def __init__(self, config: AronaSettings):
        self.config = config
        self.host = self.config.get("host")
        self.port = self.config.get("port")
        self.max_conn = self.config.get("max_connections")
        self.clients: Dict[str, ClientConnection] = {}
        self.conn_manager = ConnectionManager()

        self.bore = BoreManager(local_port=self.port, auto_reconn=True, reconn_delay=5.0)
        self.bore.on_url_change = self._handle_url_change
        self.bore.on_connected = self._handle_connected
        self.bore.on_disconnected = self._handle_disconnected

    @staticmethod #for now to stop Pycharm whining...
    async def _handle_url_change(new_url: str):
        """Called when bore URL changes"""
        console.print(f"[!] Bore URL changed: {new_url}")
        # TODO: Update DNS

    @staticmethod
    async def _handle_connected(url: str):
        """Called when bore connects"""
        console.print(f"[✓] Bore connected: {url}")

    @staticmethod
    async def _handle_disconnected():
        """Called when bore disconnects"""
        console.print(f"[!] Bore disconnected")

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        conn = ClientConnection(reader, writer)
        peer = conn.user

        if len(self.clients) >= self.max_conn:
            logger.warning(f"Too many connections, rejecting {peer} :/")
            console.print(f"[x] Too many connections, rejecting {peer}")
            writer.close()
            await writer.wait_closed()
            return

        console.print(f"[+] Connection from {peer}")
        logger.info(f"New connection from {peer} :3")

        try:
            if not await conn.do_handshake():
                console.print(f"[!] Handshake failed with {peer}")
                return

            console.print(f"[✓] Handshake complete with {peer}")

            auth_msg = await conn.read_msg()
            if auth_msg.msg_type != MessageType.AUTH:
                console.print(f"[!] Expected AUTH from {peer}")
                return

            username = auth_msg.payload.decode('utf-8').strip()
            if not username or len(username) < 2:
                reply = Message(msg_type=MessageType.AUTH_FAIL, payload=b'Invalid username')
                await conn.send_msg(reply)
                console.print(f"[!] Auth failed for {peer}: bad username")
                return

            conn.username = username
            conn.authenticated = True
            self.clients[username] = conn

            self.conn_manager.add_user(username, conn)

            reply = Message(msg_type=MessageType.AUTH_OK, payload=f'Welcome {username}!'.encode())
            await conn.send_msg(reply)

            join_msg = Message(
                msg_type=MessageType.ONLINE,
                payload=f'{username} joined'.encode()
            )
            await self.conn_manager.scream_to_channel('general', join_msg, exclude=username)

            console.print(f"[✓] {username} authenticated from {peer}")
            logger.info(f"{username} authenticated :)")

            while True:
                msg = await conn.read_msg()

                logger.info(f"{username}: {msg.msg_type.name} (id {msg.msg_id})")

                if msg.msg_type == MessageType.TEXT:
                    channel = self.conn_manager.get_user_channel(username)
                    formatted = f'[{username}] {msg.payload.decode()}'.encode()
                    broadcast_msg = Message(
                        msg_type=MessageType.TEXT,
                        payload=formatted
                    )

                    await self.conn_manager.scream_to_channel(channel, broadcast_msg, exclude=username)

                elif msg.msg_type == MessageType.DM:
                    target, dm = msg.payload.decode().split(':', 1)
                    formatted = f'[{username}] {dm}'.encode()
                    dm_msg = Message(
                        msg_type=MessageType.DM,
                        payload=formatted
                    )

                    await self.conn_manager.scream_to_user(target, dm_msg)


                elif msg.msg_type == MessageType.SUP:
                    new_channel = msg.payload.decode()
                    old_channel = self.conn_manager.get_user_channel(username)

                    if old_channel:
                        leave_msg = Message(
                            msg_type=MessageType.OFFLINE,
                            payload=f'{username} left'.encode()
                        )
                        await self.conn_manager.scream_to_channel(old_channel, leave_msg)

                    self.conn_manager.join_channel(username, new_channel)
                    join_msg = Message(
                        msg_type=MessageType.ONLINE,
                        payload=f'{username} joined'.encode()
                    )
                    await self.conn_manager.scream_to_channel(new_channel, join_msg, exclude=username)

                    confirm = Message(
                        msg_type=MessageType.SUP,
                        payload=f'Joined #{new_channel}'.encode()
                    )
                    await conn.send_msg(confirm)

                elif msg.msg_type == MessageType.ADIOS:
                    console.print(f"[!] {username} said goodbye")
                    break

                # TODO: Add/handle other msg types

        except asyncio.IncompleteReadError:
            logger.info(f"{peer} disconnected :|")
            console.print(f"[-] {peer} disconnected")

        except Exception as e:
            logger.error(f"Error with {peer}: {e} :(")
            console.print(f"[!] Error with {peer}: {e}")

        finally:
            if conn.username:
                channel = self.conn_manager.get_user_channel(conn.username)
                if channel:
                    leave_msg = Message(
                        msg_type=MessageType.OFFLINE,
                        payload=f'{conn.username} left'.encode()
                    )
                    await self.conn_manager.scream_to_channel(channel, leave_msg)

                self.conn_manager.remove_user(conn.username)

            await conn.close()

    async def start(self):
        server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        logger.info(f"Server listening on {self.host}:{self.port} :3")
        console.print(f"[*] Server listening on {self.host}:{self.port}")

        console.print("[*] Starting bore tunnel...")
        public_url = await self.bore.start()

        if public_url:
            console.print(f"[✓] Public URL: {public_url}")
        else:
            console.print("[!] Failed to start bore - server only accessible locally")

        console.print("\n[*] Server ready! Press Ctrl+C to stop\n")

        try:
            async with server:
                await server.serve_forever()

        except asyncio.CancelledError:
            pass

        finally:
            await self.stop()

    async def stop(self):
        """Cleanup on shutdown"""
        console.print("\n[*] Shutting down...")

        await self.bore.stop()

        if hasattr(self, 'conn_manager'):
            for username in list(self.conn_manager.get_all_users()):
                conn = self.conn_manager.get_connection(username)

                if conn:
                    try:
                        await conn.close()

                    except Exception as e:
                        logger.error(f"Error closing {username}: {e}")

            console.print(f"[*] Closed {len(self.conn_manager.get_all_users())} connections")
        console.print("[✓] Shutdown complete")


def main():
    try:
        asyncio.run(AronaServer(AronaSettings()).start())
    except KeyboardInterrupt:
        console.print("[*] Shutting down…")
    console.print("\n[*] Server stopped")
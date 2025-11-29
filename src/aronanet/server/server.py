import asyncio
import shlex
from rich.console import Console
from typing import Dict

from ..utils.logger import get_logger
from ..utils.config import AronaSettings
from ..protocol.messages import Message, MessageType
from .connection_manager import ConnectionManager
from .connection import ClientConnection

console = Console()
logger = get_logger("AronaServer")

async def start_bore(local_port: int, bore_token: str):
    """Start Bore as a subprocess and return the process handle"""
    cmd = f"bore local {local_port} --to {bore_token}"
    args = shlex.split(cmd)

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def log_output(stream, name):
        async for line in stream:
            print(f"[{name}] {line.decode().rstrip()}")

    asyncio.create_task(log_output(proc.stdout, "bore"))
    asyncio.create_task(log_output(proc.stderr, "bore-err"))

    return proc

class AronaServer:
    """Async raw TCP server for AoNET"""
    def __init__(self, config: AronaSettings):
        self.config = config
        self.host = self.config.get("host")
        self.port = self.config.get("port")
        self.max_conn = self.config.get("max_connections")
        self.clients: Dict[str, ClientConnection] = {}
        self.conn_manager = ConnectionManager()
        
        self.bore_proc = None

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
                    broadcast_msg = Message(msg_type=MessageType.TEXT, payload=formatted)

                    await self.conn_manager.scream_to_channel(
                        channel,
                        broadcast_msg,
                        # exclude=username
                    )

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

            conn.close()

    async def start(self):
        # Start server first
        server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        logger.info(f"Server listening on {self.host}:{self.port} :3")
        console.print(f"[*] Server listening on {self.host}:{self.port}")

        # Then start Bore
        bore_token = "bore.pub"
        self.bore_proc = await start_bore(self.port, bore_token)

        async with server:
            await server.serve_forever()

    async def stop(self):
        # Cleanup Bore
        if self.bore_proc:
            self.bore_proc.terminate()
            await self.bore_proc.wait()

if __name__ == "__main__":
    cfg = AronaSettings()
    asyncio.run(AronaServer(cfg).start())
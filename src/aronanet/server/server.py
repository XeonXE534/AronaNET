import asyncio
import shlex
from rich.console import Console
from typing import Dict
from ..utils.logger import get_logger
from ..utils.config import AronaSettings
from ..protocol.messages import Message, MessageType

console = Console()


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
        self.clients: Dict[str, asyncio.StreamWriter] = {}
        self.logger = get_logger("AronaServer")
        self.bore_proc = None

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        peer_id = str(peer)

        if len(self.clients) >= self.max_conn:
            self.logger.warning(f"Too many connections, rejecting {peer} :/")
            console.print(f"[x] Too many connections, rejecting {peer}")
            writer.close()
            await writer.wait_closed()
            return

        self.clients[peer_id] = writer
        console.print(f"[+] Connection from {peer}")
        self.logger.info(f"New connection from {peer} :3")

        try:
            while True:
                try:
                    length_bytes = await reader.readexactly(4)
                except asyncio.IncompleteReadError:
                    self.logger.info(f"{peer} Disconnected :|")
                    console.print(f"[-] {peer} disconnected")
                    break

                pack_len = int.from_bytes(length_bytes, "big")
                try:
                    pack = await reader.readexactly(pack_len)
                except asyncio.IncompleteReadError:
                    self.logger.warning(f"{peer} dropped mid-packet :[")
                    console.print(f"[*] {peer} dropped mid-packet")
                    break

                try:
                    msg = Message.unpack(pack)
                except Exception as e:
                    self.logger.error(f"Bad packet from {peer}: {type(e).__name__} - {str(e)} :[")
                    console.print(f"[!] Bad packet from {peer}: {type(e).__name__} - {str(e)}")
                    continue

                self.logger.info(f"{peer} {msg.msg_type.name} (id {msg.msg_id}) : {msg.payload} :3")

                reply = Message(msg_type=MessageType.TEXT, payload=b"ack :3")
                packed = reply.pack()

                writer.write(len(packed).to_bytes(4, "big") + packed)
                await writer.drain()

        except Exception as e:
            self.logger.error(f" Fatal error with {peer}: {e} :(")
            console.print(f"[!] Fatal error with {peer}")

        finally:
            writer.close()
            await writer.wait_closed()
            self.logger.info(f"{peer} fully closed :3")
            console.print(f"[x] {peer} fully closed")

    async def start(self):
        # Start server first
        server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        self.logger.info(f"Server listening on {self.host}:{self.port} :3")
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
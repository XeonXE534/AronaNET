import asyncio
from pyngrok import ngrok

from ..utils.logger import get_logger
from ..utils.config import AronaSettings

class AronaServer:
    def __init__(self, config: AronaSettings):
        self.config = config
        self.host = self.config.get("host", "0.0.0.0")
        self.port = self.config.get("port", 47500)
        self.max_conn = self.config.get("max_connections", 10)
        self.logger = get_logger("AronaServer")

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        user = writer.get_extra_info('peername')
        self.logger.info(f"New connection from {user}")

        while True:
            try:
                data = await reader.read(1024)
                if not data:
                    self.logger.info(f"{user} disconnected :|")
                    break

                msg = data.decode().strip()
                self.logger.info(f"From {user} received: {msg}")
                writer.write(data)
                await writer.drain()

            except ConnectionResetError:
                self.logger.info(f"{user} disconnected unexpectedly :/")
                break

            except Exception as e:
                self.logger.error(f"Error with {user}: {e} :(")
                break

        writer.close()
        await writer.wait_closed()

    async def start(self):
        tunnel = ngrok.connect(self.port, "tcp")
        self.logger.info(f"Public ngrok URL: {tunnel.public_url}")

        server = await asyncio.start_server(
            self.handle_client, self.host, self.port, limit=self.max_conn
        )
        addr = server.sockets[0].getsockname()
        self.logger.info(f"Server running on {addr}")

        async with server:
            await server.serve_forever()

if __name__ == "__main__":
    cfg = AronaSettings()
    asyncio.run(AronaServer(cfg).start())
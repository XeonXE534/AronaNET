# THIS IS A PoC TEST CLIENT!!!!!
# YES THIS WAS VIBE CODED!!!!!
# SPAM `ctrl+c` TO EXIT!!!!!!!

import asyncio
import sys
from aronanet.protocol.messages import Message, MessageType
from aronanet.protocol.crypto import SecureChannel, KeyExchange

class SimpleClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.secure_channel = SecureChannel()
        self.key_exchange = KeyExchange()
        self.username = None
        self.running = False
        self._receiver_task = None
        self._input_task = None

    async def connect(self):
        print(f"[*] Connecting to {self.host}:{self.port}...")
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        print("[✓] Connected")

    async def handshake(self):
        print("[*] Starting handshake...")
        our_pubkey = self.key_exchange.get_public_bytes()
        hi_msg = Message(msg_type=MessageType.HI, payload=our_pubkey)
        packed = hi_msg.pack()

        self.writer.write(len(packed).to_bytes(4, 'big') + packed)
        await self.writer.drain()

        length = await self.reader.readexactly(4)
        data = await self.reader.readexactly(int.from_bytes(length, 'big'))
        server_hi = Message.unpack(data)

        if server_hi.msg_type != MessageType.HI:
            raise Exception(f"Expected HI, got {server_hi.msg_type.name}")

        shared_key = self.key_exchange.derive_shared_key(server_hi.payload)
        self.secure_channel.setup_shared_key(shared_key)
        print("[✓] Handshake complete")

    async def authenticate(self, username: str):
        print(f"[*] Authenticating as '{username}'...")
        auth_msg = Message(msg_type=MessageType.AUTH, payload=username.encode())
        packed = auth_msg.pack(self.secure_channel)

        self.writer.write(len(packed).to_bytes(4, 'big') + packed)
        await self.writer.drain()

        length = await self.reader.readexactly(4)
        data = await self.reader.readexactly(int.from_bytes(length, 'big'))
        reply = Message.unpack(data, self.secure_channel)

        if reply.msg_type == MessageType.AUTH_OK:
            self.username = username
            print(f"[✓] {reply.payload.decode()}")
            return True

        else:
            print(f"[!] Auth failed: {reply.payload.decode()}")
            return False

    async def send_text(self, text: str):
        msg = Message(msg_type=MessageType.TEXT, payload=text.encode())
        packed = msg.pack(self.secure_channel)

        self.writer.write(len(packed).to_bytes(4, 'big') + packed)
        await self.writer.drain()

    async def receive_messages(self):
        try:
            while self.running:
                length = await self.reader.readexactly(4)
                data = await self.reader.readexactly(int.from_bytes(length, 'big'))
                msg = Message.unpack(data, self.secure_channel)

                if msg.msg_type == MessageType.TEXT:
                    print(f"\r{msg.payload.decode()}\n>>> ", end='', flush=True)

                elif msg.msg_type == MessageType.DM:
                    print(f"\r[DM: {msg.payload.decode()}]\n>>> ", end='', flush=True)

                elif msg.msg_type in (MessageType.ONLINE, MessageType.OFFLINE):
                    prefix = "[+]" if msg.msg_type == MessageType.ONLINE else "[-]"
                    print(f"\r{prefix} {msg.payload.decode()}\n>>> ", end='', flush=True)

        except asyncio.IncompleteReadError:
            print("\n[!] Server disconnected")

        except asyncio.CancelledError:
            pass

        except Exception as e:
            print(f"\n[!] Error receiving: {e}")

        finally:
            self.running = False

    async def input_loop(self):
        loop = asyncio.get_event_loop()
        try:
            while self.running:
                text = await loop.run_in_executor(None, input, ">>> ")
                if not self.running:
                    break

                if not text:
                    continue

                if text.startswith('/'):
                    await self.handle_command(text)

                else:
                    await self.send_text(text)
        except asyncio.CancelledError:
            pass

    async def handle_command(self, cmd: str):
        if cmd == '/quit' or cmd == '/q':
            print("[*] Disconnecting...")
            self.running = False

        elif cmd.startswith('/join ') or cmd.startswith('/j '):
            parts = cmd.split(maxsplit=1)
            if len(parts) < 2:
                print("[!] No channel specified.")

                return
            channel = parts[1].strip()

            msg = Message(msg_type=MessageType.SUP, payload=channel.encode())
            packed = msg.pack(self.secure_channel)

            self.writer.write(len(packed).to_bytes(4, 'big') + packed)
            await self.writer.drain()

            print(f"[*] Joining #{channel}...")

        elif cmd.startswith('/dm '):
            parts = cmd.split(' ', 2)
            if len(parts) < 3:
                print("Usage: /dm username message")
                return

            _, user, usr_msg = parts

            formatted = f'{user}:{usr_msg}'
            msg = Message(msg_type=MessageType.DM, payload=formatted.encode())

            packed = msg.pack(self.secure_channel)

            self.writer.write(len(packed).to_bytes(4, 'big') + packed)
            await self.writer.drain()

        elif cmd == '/clear' or cmd == '/cl':
            print("\033[2J\033[3J\033[1;1H", end='', flush=True)

        else:
            print(f"[!] Unknown command: {cmd}")

    async def run(self, username: str):
        try:
            await self.connect()
            await self.handshake()
            if not await self.authenticate(username):
                return

            self.running = True
            self._receiver_task = asyncio.create_task(self.receive_messages())
            self._input_task = asyncio.create_task(self.input_loop())

            await asyncio.wait(
                [self._receiver_task, self._input_task],
                return_when=asyncio.FIRST_COMPLETED
            )
        except ConnectionRefusedError:
            print("[!] Connection refused - is server running?")

        except Exception as e:
            print(f"[!] Error: {e}")

        finally:
            await self.close()

    async def close(self):
        """Cancel tasks and close connection"""
        self.running = False
        tasks = []
        if self._receiver_task and not self._receiver_task.done():
            self._receiver_task.cancel()
            tasks.append(self._receiver_task)

        if self._input_task and not self._input_task.done():
            self._input_task.cancel()
            tasks.append(self._input_task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()

            except Exception:
                pass
        print("[*] Client cleanup complete")

async def _main():
    if len(sys.argv) != 3:
        print("Usage: aonet-client HOST PORT")
        sys.exit(1)

    host, port = sys.argv[1], int(sys.argv[2])
    username = input("Username: ").strip()
    if not username:
        print("[!] Username required")
        sys.exit(1)

    client = SimpleClient(host, port)
    await client.run(username)

def main():
    try:
        asyncio.run(_main())

    except KeyboardInterrupt:
        print("\n[*] Exiting...")

if __name__ == "__main__":
    main()
import asyncio
import sys
from pathlib import Path

# Make sure your repo is in PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.aronanet.protocol.messages import Message, MessageType

async def run_client(host, port):
    print(f"[*] Connecting to {host}:{port}")

    try:
        reader, writer = await asyncio.open_connection(host, port)
        print("[✓] Connected!")

        # Initial message
        msg = Message(msg_type=MessageType.TEXT, payload=b"hello from PC")
        packed = msg.pack()
        writer.write(len(packed).to_bytes(4, 'big') + packed)
        await writer.drain()
        print(f"[>] Sent: {msg.payload.decode()}")

        # Read server response properly
        while True:
            resp_len_bytes = await reader.readexactly(4)
            resp_len = int.from_bytes(resp_len_bytes, 'big')
            resp_data = await reader.readexactly(resp_len)
            resp_msg = Message.unpack(resp_data)
            print(f"[<] {resp_msg.payload.decode()}")

            # Read input from user
            user_input = await asyncio.get_event_loop().run_in_executor(None, input, "> ")
            if not user_input.strip():
                continue

            msg = Message(msg_type=MessageType.TEXT, payload=user_input.strip().encode())
            packed = msg.pack()
            writer.write(len(packed).to_bytes(4, 'big') + packed)
            await writer.drain()

    except Exception as e:
        print(f"[!] Connection error: {e}")
    finally:
        writer.close()
        await writer.wait_closed()
        print("[x] Connection closed")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python termux.py HOST PORT")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    asyncio.run(run_client(host, port))

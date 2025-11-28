import asyncio
import sys


async def test_connect(host, port):
    """Simple client to test connection"""

    print(f"[*] Connecting to {host}:{port}")

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=10.0
        )

        print("[✓] Connected!")

        # Send test message
        msg = b"hello from termux"
        length = len(msg).to_bytes(4, 'big')

        writer.write(length + msg)
        await writer.drain()
        print(f"[>] Sent: {msg.decode()}")

        # Read response
        resp_length = await reader.readexactly(4)
        resp_msg = await reader.readexactly(int.from_bytes(resp_length, 'big'))
        print(f"[<] Received: {resp_msg.decode()}")

        # Keep connection open for manual testing
        print("\n[*] Connection open. Type messages (Ctrl+C to quit):")

        while True:
            # Read from stdin
            user_input = await asyncio.get_event_loop().run_in_executor(
                None, sys.stdin.readline
            )

            if not user_input:
                break

            msg = user_input.strip().encode()
            length = len(msg).to_bytes(4, 'big')

            writer.write(length + msg)
            await writer.drain()

            # Read response
            resp_length = await reader.readexactly(4)
            resp_msg = await reader.readexactly(int.from_bytes(resp_length, 'big'))
            print(f"[<] {resp_msg.decode()}")

        writer.close()
        await writer.wait_closed()

    except asyncio.TimeoutError:
        print("[!] Connection timeout")
    except ConnectionRefusedError:
        print("[!] Connection refused")
    except Exception as e:
        print(f"[!] Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python test_client_termux.py HOST PORT")
        print("Example: python test_client_termux.py bore.pub 54321")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])

    asyncio.run(test_connect(host, port))
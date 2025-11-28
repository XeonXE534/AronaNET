# test_local_server.py
import asyncio

async def handle_echo(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"[+] Connection from {addr}")

    while True:
        try:
            # Read length prefix
            length_bytes = await reader.readexactly(4)
            length = int.from_bytes(length_bytes, 'big')

            # Read message
            data = await reader.readexactly(length)
            message = data.decode()

            print(f"[<] {message}")

            # Echo back
            writer.write(length_bytes + data)
            await writer.drain()

        except asyncio.IncompleteReadError:
            print(f"[-] {addr} disconnected")
            break
        except Exception as e:
            print(f"[!] Error: {e}")
            break

    writer.close()
    await writer.wait_closed()


async def main():
    server = await asyncio.start_server(
        handle_echo, '0.0.0.0', 47500
    )

    print(f"[*] Server listening on 0.0.0.0:47500")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
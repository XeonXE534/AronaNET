# test_serveo.py
import asyncio
import re

from .test_server import handle_echo


async def start_serveo_tunnel(local_port):
    """
    Connect to Serveo and get public URL
    Returns: (process, public_url)
    """

    # Start SSH process
    process = await asyncio.create_subprocess_exec(
        'ssh',
        '-R', f'0:localhost:{local_port}',  # 0 = random port
        'serveo.net',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    print("[*] Connecting to Serveo...")

    # Serveo prints the URL to stderr (yeah, weird)
    public_url = None

    # Read first few lines to get URL
    for _ in range(10):
        line = await process.stderr.readline()
        line = line.decode().strip()

        print(f"[DEBUG] {line}")

        # Look for: "Forwarding TCP connections from serveo.net:12345"
        match = re.search(r'serveo\.net:(\d+)', line)
        if match:
            port = match.group(1)
            public_url = f"tcp://serveo.net:{port}"
            print(f"[+] Public URL: {public_url}")
            break

    if not public_url:
        print("[!] Failed to get Serveo URL")
        process.terminate()
        return None, None

    return process, public_url


async def test_serveo():
    """Full test: start server + tunnel"""

    local_port = 47500

    # Start local server (same as step 1)
    server = await asyncio.start_server(
        handle_echo, '127.0.0.1', local_port
    )
    print(f"[*] Local server on port {local_port}")

    # Start Serveo tunnel
    tunnel_proc, public_url = await start_serveo_tunnel(local_port)

    if not public_url:
        return

    print(f"\n{'=' * 50}")
    print(f"[✓] Server is public at: {public_url}")
    print(f"{'=' * 50}\n")
    print("Press Ctrl+C to stop...")

    try:
        # Keep running
        async with server:
            await server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
        tunnel_proc.terminate()


if __name__ == "__main__":
    asyncio.run(test_serveo())
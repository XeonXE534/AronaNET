import asyncio
import re
import shlex
from typing import Optional, Callable, Awaitable

from ..utils.logger import get_logger

logger = get_logger("BoreManager")

class BoreManager:
    """Manages bore tunnel with monitoring and auto-reconnect"""
    def __init__(self, local_port: int, bore_server: str = "bore.pub", auto_reconn: bool = True, reconn_delay: float = 5.0):
        self.local_port = local_port
        self.bore_server = bore_server
        self.auto_reconn = auto_reconn
        self.reconn_delay = reconn_delay

        self.process: Optional[asyncio.subprocess.Process] = None
        self.current_url: Optional[str] = None
        self.is_running = False
        self._shutdown = False

        self.on_url_change: Optional[Callable[[str], Awaitable[None]]] = None
        self.on_connected: Optional[Callable[[str], Awaitable[None]]] = None
        self.on_disconnected: Optional[Callable[[], Awaitable[None]]] = None

        self._monitor_task: Optional[asyncio.Task] = None
        self._stdout_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None

        logger.info(f"BoreManager initialized for port {local_port}")

    async def start(self) -> Optional[str]:
        """Start bore tunnel and return public URL"""
        if self.is_running:
            logger.warning("Bore already running :]")
            return self.current_url

        if self._shutdown:
            logger.error("Cannot start, manager is offline :/")
            return None

        logger.info(f"Starting bore tunnel: {self.local_port} -> {self.bore_server} :3")

        try:
            cmd = f"bore local {self.local_port} --to {self.bore_server}"
            args = shlex.split(cmd)

            self.process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr = asyncio.subprocess.PIPE
            )

            self.is_running = True
            logger.debug("bore process started, waiting for URL...")

            url = await self._wait_for_url()

            if not url:
                logger.error("Failed to get bore URL :(")
                await self._cleanup()
                return None

            self.current_url = url
            logger.info(f"Bore tunnel established: {url}")

            self._stdout_task = asyncio.create_task(
                self._read_stdout(),
                name="bore-stdout"
            )
            self._stderr_task = asyncio.create_task(
                self._read_stderr(),
                name="bore-stderr"
            )
            self._monitor_task = asyncio.create_task(
                self._monitor_process(),
                name="bore-monitor"
            )

            if self.on_connected:
                try:
                    await self.on_connected(url)
                except Exception as e:
                    logger.error(f"Error in on_connected callback: {e}")

            return url

        except FileNotFoundError:
            logger.error("bore command not found - is it installed?")
            logger.error("Install with: cargo install bore-cli")
            self.is_running = False
            return None

        except Exception as e:
            logger.error(f"Failed to start bore: {e}")
            self.is_running = False
            await self._cleanup()
            return None

    async def _wait_for_url(self, timeout: float = 15.0) -> Optional[str]:
        """
        Wait for bore to output the public URL

        Args:
            timeout: Max seconds to wait for URL

        Returns:
            URL string or None if timeout/failure
        """
        try:
            start_time = asyncio.get_event_loop().time()

            while True:
                elapsed = asyncio.get_event_loop().time() - start_time

                if elapsed > timeout:
                    logger.error(f"Timeout waiting for bore URL ({timeout}s)")
                    return None

                try:
                    line = await asyncio.wait_for(
                        self.process.stdout.readline(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                if not line:
                    logger.warning("bore stdout closed without providing URL")
                    return None

                line = line.decode().strip()
                if not line:
                    continue

                clean_line = self._strip_ansi(line)
                logger.debug(f"bore: {clean_line}")

                # Format: 2025-11-30T08:38:27.332408Z  INFO bore_cli::client: connected to server remote_port=6969
                match = re.search(r'listening at ([a-z0-9.-]+):(\d+)', clean_line, re.IGNORECASE)

                if match:
                    host = match.group(1)
                    port = match.group(2)
                    url = f"AoNET/TCP://{host}:{port}"
                    logger.info(f"Parsed URL from bore output: {url}")
                    return url

        except Exception as e:
            logger.error(f"Error parsing bore URL: {e}")
            return None

    @staticmethod
    def _strip_ansi(text: str) -> str:
        """
        Remove ANSI color/formatting codes from text

        Args:
            text: Raw text with potential ANSI codes

        Returns:
            Clean text without ANSI codes
        """
        # Matches: \x1b[...m or \033[...m or just [...mA
        ansi_pattern = r'\x1b\[[0-9;]*m|\033\[[0-9;]*m|\[[0-9;]*m'
        return re.sub(ansi_pattern, '', text)

    async def _read_stdout(self):
        """Read and log stdout (bore's main output stream)"""
        if not self.process or not self.process.stdout:
            return

        try:
            async for line in self.process.stdout:
                if self._shutdown:
                    break

                line = line.decode().rstrip()
                if line:
                    clean = self._strip_ansi(line)
                    logger.debug(f"bore stdout: {clean}")

        except asyncio.CancelledError:
            logger.debug("stdout reader cancelled")

        except Exception as e:
            logger.error(f"Error reading stdout: {e}")

    async def _read_stderr(self):
        """Read and log stderr (errors and warnings)"""
        if not self.process or not self.process.stderr:
            return

        try:
            async for line in self.process.stderr:
                if self._shutdown:
                    break

                line = line.decode().rstrip()
                if line:
                    clean = self._strip_ansi(line)

                    if any(word in clean.lower() for word in ['error', 'fatal', 'failed']):
                        logger.error(f"bore stderr: {clean}")

                    elif 'warn' in clean.lower():
                        logger.warning(f"bore stderr: {clean}")

                    else:
                        logger.debug(f"bore stderr: {clean}")

        except asyncio.CancelledError:
            logger.debug("stderr reader cancelled")

        except Exception as e:
            logger.error(f"Error reading stderr: {e}")

    async def _monitor_process(self):
        """Monitor process health and handle reconnection"""
        if not self.process:
            return

        try:
            return_code = await self.process.wait()

            logger.warning(f"bore process exited with code {return_code} :|")
            self.is_running = False

            if self.on_disconnected:
                try:
                    await self.on_disconnected()

                except Exception as e:
                    logger.error(f"Error in on_disconnected callback: {e}")

            if self.auto_reconn and not self._shutdown:
                logger.info(f"Auto-reconnecting in {self.reconn_delay}s...")
                await asyncio.sleep(self.reconn_delay)

                if not self._shutdown:
                    new_url = await self.start()

                    if new_url and new_url != self.current_url:
                        logger.warning(f"URL changed after reconnect: {self.current_url} -> {new_url} :3")

                        if self.on_url_change:
                            try:
                                await self.on_url_change(new_url)

                            except Exception as e:
                                logger.error(f"Error in on_url_change callback: {e} :/")
                else:
                    logger.info("Auto-reconnect disabled, tunnel will remain down :|")

        except asyncio.CancelledError:
            logger.debug("Monitor task cancelled")

        except Exception as e:
            logger.error(f"Error monitoring bore: {e}")

    async def _cleanup(self):
        """Terminate process and cleanup"""
        if self.process:
            try:
                self.process.terminate()

                try:
                    await asyncio.wait_for(self.process.wait(), timeout=3.0)
                    logger.debug("bore process terminated gracefully")

                except asyncio.TimeoutError:
                    logger.warning("bore didn't terminate, killing...")
                    self.process.kill()
                    await self.process.wait()
                    logger.debug("bore process killed")

            except Exception as e:
                logger.error(f"Error terminating bore process: {e}")

            finally:
                self.process = None

    async def stop(self):
        """Stop bore tunnel and cleanup all resources"""
        if not self.is_running and not self.process:
            logger.debug("Bore not running, nothing to stop :|")
            return

        logger.info("Stopping bore tunnel... :3")

        self._shutdown = True
        self.is_running = False

        tasks = [self._monitor_task, self._stdout_task, self._stderr_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()

        pending = [t for t in tasks if t and not t.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        await self._cleanup()

        self.current_url = None
        self._monitor_task = None
        self._stderr_task = None
        self._stdout_task = None

        logger.info("Bore tunnel stopped")

    async def restart(self) -> Optional[str]:
        """Restart bore tunnel"""
        logger.info("Restarting bore tunnel... :3")

        await self.stop()
        await asyncio.sleep(1.0)

        self._shutdown = False
        return await self.start()

    def get_url(self) -> Optional[str]:
        """Get current public URL"""
        return self.current_url if self.is_running else None

    def is_alive(self) -> bool:
        """Check if tunnel is currently running"""
        return self.is_running and self.process is not None

    def get_status(self) -> dict:
        """Get detailed status information"""
        return {
            'running': self.is_running,
            'url': self.current_url,
            'local_port': self.local_port,
            'bore_server': self.bore_server,
            'auto_reconnect': self.auto_reconn,
            'process_alive': self.process is not None,
        }

    async def __aenter__(self):
        """Context manager entry"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.stop()
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.aronanet.server.bore_manager import BoreManager

@pytest.mark.asyncio
async def test_strip_ansi():
    dirty = "\x1b[31mhello\x1b[0m"
    clean = BoreManager._strip_ansi(dirty)
    assert clean == "hello"


@pytest.mark.asyncio
async def test_wait_for_url_parses_correctly():
    bm = BoreManager(local_port=9000)

    # Fake process with mocked stdout
    bm.process = MagicMock()
    bm.process.stdout = AsyncMock()

    # Lines that BoreManager should parse
    bm.process.stdout.readline = AsyncMock(
        side_effect=[
            b"2025-11-30 INFO something\n",
            b"listening at bore.pub:12345\n",
            b"",  # end of stream
        ]
    )

    url = await bm._wait_for_url()
    assert url == "AoNET/TCP://bore.pub:12345"


@pytest.mark.asyncio
async def test_start_success():
    bm = BoreManager(local_port=8080)

    fake_process = MagicMock()
    fake_process.stdout = AsyncMock()
    fake_process.stderr = AsyncMock()

    # Noise → then valid URL
    fake_process.stdout.readline = AsyncMock(
        side_effect=[
            b"garbage\n",
            b"listening at bore.pub:9999\n",
        ]
    )

    with patch("asyncio.create_subprocess_exec", return_value=fake_process):
        url = await bm.start()

    assert url == "AoNET/TCP://bore.pub:9999"
    assert bm.is_running
    assert bm.current_url == url


@pytest.mark.asyncio
async def test_start_fails_command_not_found():
    bm = BoreManager(local_port=4040)

    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
        url = await bm.start()

    assert url is None
    assert bm.is_running is False


@pytest.mark.asyncio
async def test_stop_cleans_up_tasks():
    bm = BoreManager(local_port=7777)

    bm.process = MagicMock()
    bm.process.wait = AsyncMock(return_value=0)

    # Fake running tasks
    t1 = asyncio.create_task(asyncio.sleep(0))
    t2 = asyncio.create_task(asyncio.sleep(0))
    t3 = asyncio.create_task(asyncio.sleep(0))

    bm._monitor_task = t1
    bm._stdout_task = t2
    bm._stderr_task = t3

    await bm.stop()

    assert bm.is_running is False
    assert bm.current_url is None
    assert bm.process is None


@pytest.mark.asyncio
async def test_context_manager():
    bm = BoreManager(local_port=8000)

    fake_process = MagicMock()
    fake_process.stdout = AsyncMock()
    fake_process.stderr = AsyncMock()

    fake_process.stdout.readline = AsyncMock(
        side_effect=[
            b"listening at bore.pub:5555\n",
        ]
    )

    with patch("asyncio.create_subprocess_exec", return_value=fake_process):
        async with bm as manager:
            assert manager.is_alive()
            assert manager.current_url == "AoNET/TCP://bore.pub:5555"

        # After exit, everything must be dead
        assert bm.is_alive() is False

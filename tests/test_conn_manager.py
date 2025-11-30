import pytest
from unittest.mock import MagicMock, AsyncMock

from aronanet.server.connection_manager import ConnectionManager
from aronanet.server.connection import ClientConnection
from aronanet.protocol.messages import Message, MessageType

def test_init():
    """Test ConnectionManager initializes correctly"""
    cm = ConnectionManager()

    assert "general" in cm.channels
    assert isinstance(cm.channels["general"], set)
    assert len(cm.connections) == 0


def test_add_user():
    """Test adding a user"""
    cm = ConnectionManager()

    # Mock connection
    conn = MagicMock(spec=ClientConnection)

    cm.add_user("alice", conn)

    assert "alice" in cm.connections
    assert "alice" in cm.channels["general"]
    assert cm.user_channels["alice"] == "general"


def test_remove_user():
    """Test removing a user"""
    cm = ConnectionManager()
    conn = MagicMock(spec=ClientConnection)

    cm.add_user("alice", conn)
    cm.remove_user("alice")

    assert "alice" not in cm.connections
    assert "alice" not in cm.channels["general"]
    assert "alice" not in cm.user_channels


def test_join_channel():
    """Test joining a new channel"""
    cm = ConnectionManager()
    conn = MagicMock(spec=ClientConnection)

    cm.add_user("alice", conn)
    cm.join_channel("alice", "gaming")

    assert "gaming" in cm.channels
    assert "alice" in cm.channels["gaming"]
    assert "alice" not in cm.channels["general"]
    assert cm.user_channels["alice"] == "gaming"


@pytest.mark.asyncio
async def test_scream_to_channel():
    """Test broadcasting to channel"""
    cm = ConnectionManager()

    # Mock connections
    alice = MagicMock(spec=ClientConnection)
    alice.send_msg = AsyncMock()

    bob = MagicMock(spec=ClientConnection)
    bob.send_msg = AsyncMock()

    cm.add_user("alice", alice)
    cm.add_user("bob", bob)

    # Broadcast
    msg = Message(msg_type=MessageType.TEXT, payload=b"hello")
    await cm.scream_to_channel("general", msg)

    # Both should receive
    alice.send_msg.assert_called_once()
    bob.send_msg.assert_called_once()


@pytest.mark.asyncio
async def test_scream_excludes_sender():
    """Test broadcast excludes sender"""
    cm = ConnectionManager()

    alice = MagicMock(spec=ClientConnection)
    alice.send_msg = AsyncMock()

    bob = MagicMock(spec=ClientConnection)
    bob.send_msg = AsyncMock()

    cm.add_user("alice", alice)
    cm.add_user("bob", bob)

    # Broadcast excluding alice
    msg = Message(msg_type=MessageType.TEXT, payload=b"hello")
    await cm.scream_to_channel("general", msg, exclude="alice")

    # Only bob receives
    alice.send_msg.assert_not_called()
    bob.send_msg.assert_called_once()
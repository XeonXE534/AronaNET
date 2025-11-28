# AronaNET

A custom peer-to-peer chat protocol built from scratch, featuring raw TCP networking, AES-256 encryption, and multi-platform clients.

---

## Features

-  **End-to-End Encryption** - AES-256 encryption on all messages
-  **Multi-Platform** - Terminal (Linux/macOS/Windows), Mobile (Android)
-  **Channels & DMs** - Organized channels and private messaging
-  **File Sharing** - Chunked image transfer protocol
-  **Self-Hosted** - Run your own node, own your data
-  **Low Latency** - Custom binary protocol over raw TCP
-  **Blue Archive Themed** - Arona-inspired UI and aesthetics

---

## Why AronaNET?

AronaNET is a learning project exploring low-level networking, protocol design, and distributed systems. Unlike traditional chat applications that rely on HTTP/WebSocket and existing frameworks, AronaNET implements:

- **Custom binary protocol** over raw TCP sockets
- **Manual encryption layer** using AES-256
- **Protocol specification** designed from scratch
- **Multi-platform clients** with unified backend

**This is not meant to replace Discord or Telegram.** It's an educational project demonstrating networking fundamentals and protocol design.

---
## Documentation

### Protocol Specification

**AronaNET Transport Protocol v1.0 (ArTP/1.0)**

**Wire Format:**
```
[4 bytes: message length (big-endian)]
[N bytes: AES-256 encrypted JSON payload]
```

**Message Types:**
- `AUTH` - Client authentication
- `MSG` - Chat message (channel or DM)
- `JOIN` - Join channel
- `PART` - Leave channel
- `PING/PONG` - Keep-alive
- `IMG_CHUNK` - Image file transfer
- `ERROR` - Error response

**Example Message:**
```json
{
  "version": "1.0",
  "type": "MSG",
  "from": "sensei",
  "dest_type": "channel",
  "dest": "#general",
  "content": "Hello Arona!",
  "timestamp": 1234567890
}
```

Full protocol specification: [PROTOCOL.md](docs/PROTOCOL.md)

---

## 🏗️ Architecture
```
    ┌─────────────────────────────────────────┐
    │                     CLIENTS             │
    │  [Terminal]      [Mobile]               │
    │   TCP+AES        WebSocket+AES          │
    └────────────────────┬────────────────────┘
                         │
                         v
              ┌──────────────────────┐
              │   ngrok TCP Tunnel   │
              │  (NAT Traversal)     │
              └──────────────────────┘
                         │
                         v
┌─────────────────────────────────────────────────────────┐
│                  ARONANET SERVER                        │
│  • Connection Manager (TCP + WebSocket)                 │
│  • Protocol Handler (Encryption, Parsing)               │
│  • Router (Channels, DMs, Broadcasting)                 │
│  • Auto-Discovery (GitHub Gist URL Publishing)          │
└─────────────────────────────────────────────────────────┘
```

**Key Components:**

- **Server** - Python asyncio-based server handling TCP and WebSocket
- **Protocol** - Custom JSON-over-TCP with AES encryption
- **Terminal Client** - Textual-based TUI for power users
- **Mobile Client** - React Native app for casual users
- **Auto-Discovery** - Clients fetch server URL from GitHub Gist automatically

---

## 🛠️ Tech Stack

**Backend:**
- Python 3.10+ (asyncio, socket)
- `cryptography` (AES-256 encryption)
- ngrok (NAT traversal)

**Terminal Client:**
- Python
- Textual (Terminal UI framework)

**Mobile Client:**
- React Native
- TypeScript
- WebSocket client

**Infrastructure:**
- ngrok for tunneling
- GitHub Gist for auto-discovery
- Self-hosted (no cloud dependency)

---

## 📦 Project Structure
```
AronaNET/
├── src/
│   ├── server/
│   │   ├── __init__.py
│   │   ├── server.py          # Main server
│   │   ├── protocol.py        # Protocol handler
│   │   └── router.py          # Message routing
│   ├── terminal/
│   │   ├── __init__.py
│   │   ├── client.py          # Terminal client
│   │   └── ui.py              # Textual UI
│   ├── mobile/                # React Native app
│   │   ├── src/
│   │   └── App.tsx
│   └── common/
│       ├── crypto.py          # Encryption utilities
│       ├── discovery.py       # Auto-discovery
│       └── protocol.py        # Protocol definitions
├── docs/
│   └── PROTOCOL.md           # Protocol specification
├── tests/
├── pyproject.toml
├── README.md
└── LICENSE
```

## Roadmap

- [ ] TCP server with custom protocol
- [ ] Terminal client (Linux/macOS/Windows)
- [ ] Mobile client (Android)
- [ ] Auto-discovery
- [ ] Encryption (AES-256)
- [ ] Image sharing

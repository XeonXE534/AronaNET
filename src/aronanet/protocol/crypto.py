from cryptography.hazmat.primitives.asymmetric import x25519 as exchange
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305 as cipher
import os

from ..utils.logger import get_logger

logger = get_logger("Crypto")

server_private = exchange.X25519PrivateKey.generate()
server_public = server_private.public_key()

client_private = exchange.X25519PrivateKey.generate()
client_public = client_private.public_key()

shared_key_server = server_private.exchange(client_public)
shared_key_client = client_private.exchange(server_public)

if shared_key_server != shared_key_client:
    logger.error("Shared key mismatch :(")
    raise ValueError("Key mismatch")

else:
    logger.info("Shared key established :)")

KEY = shared_key_server[:32]

def encrypt(data: bytes) -> tuple[bytes, bytes]:
    """Encrypt payload -> (nonce, ciphertext)"""
    nonce = os.urandom(12)
    chacha = cipher(KEY)
    ciphertext = chacha.encrypt(nonce, data, None)
    return nonce, ciphertext

def decrypt(nonce: bytes, ciphertext: bytes) -> bytes:
    """Decrypt payload"""
    chacha = cipher(KEY)
    return chacha.decrypt(nonce, ciphertext, None)

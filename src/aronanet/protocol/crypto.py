from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives import serialization
import os

from ..utils.logger import get_logger

logger = get_logger("Crypto")

class SecureChannel:
    """Encryption channel for one connection"""
    def __init__(self):
        self.cipher = None
        self.shared_key = None
        logger.debug("SecureChannel init :3")

    def setup_shared_key(self, shared_key: bytes):
        """Initialize cipher with derived shared key"""
        if len(shared_key) < 32:
            logger.error("Shared key too short :(")
            raise ValueError("Shared key too short :(")

        self.shared_key = shared_key[:32]
        self.cipher = ChaCha20Poly1305(self.shared_key)
        logger.info("Cipher init with shared key :3")

    def encrypt(self, data: bytes) -> tuple[bytes, bytes]:
        """Encrypt payload -> (nonce, ciphertext)"""
        if not self.cipher:
            logger.error("Cipher not init :(")
            raise RuntimeError("Cipher not init :(")

        nonce = os.urandom(12)
        ciphertext = self.cipher.encrypt(nonce, data, None)

        logger.debug(f"Encrypted {len(data)} bytes -> {len(ciphertext)} bytes :3")
        return nonce, ciphertext

    def decrypt(self, nonce: bytes, ciphertext:bytes) -> bytes:
        """Decrypt payload"""
        if not self.cipher:
            logger.error("Cipher not init :(")
            raise RuntimeError("Cipher not init :(")

        plaintext = self.cipher.decrypt(nonce, ciphertext, None)

        logger.debug(f"Decrypted {len(ciphertext)} bytes -> {len(ciphertext)} bytes :3")
        return plaintext

class KeyExchange:
    def __init__(self):
        """X25519 key exchange for connection setup"""
        self.private_key = x25519.X25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        logger.debug("KeyExchange initialized with new keypair :3")

    def get_public_bytes(self) -> bytes:
        """Get public key as raw bytes for transmission"""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

    def derive_shared_key(self, peer_public_bytes: bytes):
        """Perform key exchange with peer's public key"""
        try:
            peer_public_bytes = x25519.X25519PublicKey.from_public_bytes(peer_public_bytes)
            shared_key = self.private_key.exchange(peer_public_bytes)

            logger.info("Shared key derived succesfully :3")
            return shared_key

        except Exception as e:
            logger.error(f"Key exhange failed: {e} :(")
            raise
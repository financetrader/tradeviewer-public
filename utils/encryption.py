"""Credential encryption and decryption utilities."""
import os
from cryptography.fernet import Fernet, InvalidToken
from base64 import urlsafe_b64encode
import hashlib


class CredentialEncryption:
    """Handles encryption and decryption of sensitive credentials."""

    @staticmethod
    def _get_encryption_key():
        """
        Get or generate the encryption key.
        In production, this should come from a secure key management service (AWS KMS, Vault, etc).
        """
        # Try to get from environment first (recommended for production)
        key_env = os.getenv('ENCRYPTION_KEY')
        if key_env:
            return key_env.encode() if isinstance(key_env, str) else key_env

        # Fallback: generate from a derived key (less secure, for development only)
        # In production, NEVER rely on this fallback
        fallback_seed = os.getenv('ENCRYPTION_KEY_SEED', 'default-dev-seed-change-in-production')

        # Derive a key from the seed using PBKDF2-like approach
        derived = hashlib.sha256(fallback_seed.encode()).digest()
        # Fernet requires base64-encoded 32-byte keys
        key = urlsafe_b64encode(derived)
        return key

    @staticmethod
    def encrypt(plaintext):
        """Encrypt sensitive data."""
        if not plaintext:
            return None

        try:
            key = CredentialEncryption._get_encryption_key()
            f = Fernet(key)
            encrypted = f.encrypt(plaintext.encode() if isinstance(plaintext, str) else plaintext)
            return encrypted.decode()
        except Exception as e:
            print(f"Encryption error: {e}")
            raise ValueError(f"Failed to encrypt credential: {str(e)}")

    @staticmethod
    def decrypt(ciphertext):
        """Decrypt sensitive data."""
        if not ciphertext:
            return None

        try:
            key = CredentialEncryption._get_encryption_key()
            f = Fernet(key)
            decrypted = f.decrypt(ciphertext.encode() if isinstance(ciphertext, str) else ciphertext)
            return decrypted.decode()
        except InvalidToken:
            print("Invalid encryption token - possible key mismatch or corrupted data")
            return None
        except Exception as e:
            print(f"Decryption error: {e}")
            return None


def encrypt_credential(plaintext):
    """Convenience function to encrypt a credential."""
    return CredentialEncryption.encrypt(plaintext)


def decrypt_credential(ciphertext):
    """Convenience function to decrypt a credential."""
    return CredentialEncryption.decrypt(ciphertext)

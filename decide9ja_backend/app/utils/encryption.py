"""
Phone Number Encryption Utility for Decide9ja.

Provides secure, reversible encryption for phone numbers to enable:
- Proactive WhatsApp notifications
- Breaking news alerts
- Election reminders
- Poll distribution

Uses Fernet symmetric encryption (AES-128-CBC with HMAC).
The encryption key should be stored securely in environment variables.
"""
import os
import hashlib
import logging
from typing import Optional, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)

# Try to import cryptography, provide fallback if not installed
# Use lazy import to avoid crashing on broken cryptography installs
CRYPTO_AVAILABLE = False
_fernet_module = None


def _try_import_crypto():
    """Lazy import of cryptography to handle broken installs."""
    global CRYPTO_AVAILABLE, _fernet_module
    if _fernet_module is not None:
        return CRYPTO_AVAILABLE

    try:
        import cryptography.fernet as _fm
        _fernet_module = _fm
        CRYPTO_AVAILABLE = True
    except Exception:
        CRYPTO_AVAILABLE = False
        _fernet_module = False  # Mark as attempted

    return CRYPTO_AVAILABLE


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.
    Run this once and store the result in PHONE_ENCRYPTION_KEY env var.

    Usage:
        python -c "from app.utils.encryption import generate_encryption_key; print(generate_encryption_key())"
    """
    if not _try_import_crypto():
        raise ImportError("cryptography library not installed or broken")
    return _fernet_module.Fernet.generate_key().decode()


@lru_cache(maxsize=1)
def _get_fernet():
    """Get or create the Fernet cipher instance."""
    if not _try_import_crypto():
        return None

    key = os.getenv('PHONE_ENCRYPTION_KEY')
    if not key:
        logger.warning("PHONE_ENCRYPTION_KEY not set - phone encryption disabled")
        return None

    try:
        return _fernet_module.Fernet(key.encode())
    except Exception as e:
        logger.error(f"Invalid encryption key: {e}")
        return None


def normalize_phone(phone: str) -> str:
    """
    Normalize phone number to consistent format.

    Examples:
        +234 801 234 5678 -> +2348012345678
        08012345678 -> +2348012345678
        234-801-234-5678 -> +2348012345678
    """
    if not phone:
        return ""

    # Remove spaces, dashes, parentheses
    cleaned = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    # Handle Nigerian numbers
    if cleaned.startswith("0") and len(cleaned) == 11:
        # Local format: 08012345678 -> +2348012345678
        cleaned = "+234" + cleaned[1:]
    elif cleaned.startswith("234") and not cleaned.startswith("+"):
        # Missing plus: 2348012345678 -> +2348012345678
        cleaned = "+" + cleaned
    elif not cleaned.startswith("+"):
        # Assume Nigerian if no country code
        cleaned = "+234" + cleaned

    return cleaned


def hash_phone(phone: str) -> str:
    """
    Create SHA256 hash of phone number for indexing/lookups.
    This is one-way and cannot be reversed.
    """
    normalized = normalize_phone(phone)
    return hashlib.sha256(normalized.encode()).hexdigest()


def encrypt_phone(phone: str) -> Optional[str]:
    """
    Encrypt a phone number for storage.
    Returns None if encryption is not available.

    The encrypted value can be decrypted later with decrypt_phone().
    """
    fernet = _get_fernet()
    if not fernet:
        return None

    try:
        normalized = normalize_phone(phone)
        encrypted = fernet.encrypt(normalized.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Failed to encrypt phone: {e}")
        return None


def decrypt_phone(encrypted_phone: str) -> Optional[str]:
    """
    Decrypt an encrypted phone number.
    Returns None if decryption fails or is not available.
    """
    fernet = _get_fernet()
    if not fernet:
        return None

    try:
        decrypted = fernet.decrypt(encrypted_phone.encode())
        return decrypted.decode()
    except Exception as e:
        # Catch InvalidToken and other decryption errors
        if "InvalidToken" in type(e).__name__ or "invalid" in str(e).lower():
            logger.error("Invalid token - phone could not be decrypted")
        else:
            logger.error(f"Failed to decrypt phone: {e}")
        return None


def process_phone(phone: str) -> Tuple[str, Optional[str]]:
    """
    Process a phone number for storage.

    Returns:
        (phone_hash, encrypted_phone)

    The hash is always returned for indexing.
    The encrypted phone is returned if encryption is available.
    """
    phone_hash = hash_phone(phone)
    encrypted = encrypt_phone(phone)
    return phone_hash, encrypted


def get_phone_for_messaging(encrypted_phone: str) -> Optional[str]:
    """
    Get the actual phone number for sending messages.

    This is the only function that should be used to retrieve
    phone numbers for WhatsApp/SMS messaging.
    """
    phone = decrypt_phone(encrypted_phone)
    if phone:
        # Format for Twilio WhatsApp
        return f"whatsapp:{phone}"
    return None


def can_send_proactive_messages() -> bool:
    """Check if proactive messaging is enabled (encryption key is set)."""
    return _get_fernet() is not None


# Convenience function for migration
def migrate_hash_to_encrypted(phone_hash: str, raw_phone: str) -> Optional[str]:
    """
    Helper for migrating existing users.

    If you have access to the raw phone (e.g., from Twilio logs),
    you can use this to add encrypted phone to existing records.
    """
    # Verify the hash matches
    if hash_phone(raw_phone) != phone_hash:
        logger.error("Phone hash mismatch - cannot migrate")
        return None

    return encrypt_phone(raw_phone)

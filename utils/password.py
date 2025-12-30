#!/usr/bin/env python3
"""
Password hashing utilities using bcrypt.
Provides secure password storage with automatic migration from plaintext.
"""

import bcrypt
import re


def is_bcrypt_hash(password: str) -> bool:
    """Check if a string is a bcrypt hash."""
    # bcrypt hashes start with $2a$, $2b$, or $2y$ followed by cost factor
    return bool(re.match(r'^\$2[aby]\$\d{2}\$.{53}$', password))


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, stored_password: str) -> bool:
    """
    Verify a password against a stored password.
    Handles both bcrypt hashes and legacy plaintext passwords.
    
    Returns:
        True if password matches, False otherwise.
    """
    if is_bcrypt_hash(stored_password):
        # Stored password is a bcrypt hash
        try:
            return bcrypt.checkpw(
                plain_password.encode('utf-8'),
                stored_password.encode('utf-8')
            )
        except Exception:
            return False
    else:
        # Legacy plaintext password - direct comparison
        # Note: This is for backward compatibility only
        return plain_password == stored_password


def needs_rehash(stored_password: str) -> bool:
    """Check if a password needs to be rehashed (is plaintext)."""
    return not is_bcrypt_hash(stored_password)

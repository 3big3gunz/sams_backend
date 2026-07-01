import hashlib
import os
import datetime
from typing import Union, Optional
from jose import jwt, JWTError

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "supersecretattendancekey1234567890!")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

def hash_password(password: str) -> str:
    """Hash a password using PBKDF2 HMAC SHA-256 (standard library, highly portable)."""
    salt = os.urandom(16)
    iterations = 100000
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    # Store salt, iterations, and key as hex
    return f"{salt.hex()}:{iterations}:{key.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its PBKDF2 hash."""
    try:
        salt_hex, iter_str, key_hex = hashed_password.split(":")
        salt = bytes.fromhex(salt_hex)
        iterations = int(iter_str)
        key = bytes.fromhex(key_hex)
        
        new_key = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt, iterations)
        return new_key == key
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

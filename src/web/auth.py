# src/web/auth.py
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Cookie, Depends, HTTPException
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from src.core.config import settings

password_hash = PasswordHash((BcryptHasher(),))


def create_access_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    """Encode a JWT with expiry. Default expiry from settings.JWT_EXPIRE_MINUTES (480 = 8h)."""
    to_encode = data.copy()
    expires = expires_minutes or settings.JWT_EXPIRE_MINUTES
    expire = datetime.utcnow() + timedelta(minutes=expires)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against stored bcrypt hash."""
    try:
        return password_hash.verify(plain_password, hashed_password)
    except Exception:
        return False


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password with bcrypt."""
    return password_hash.hash(plain_password)


def get_current_user_from_cookie(access_token: str = Cookie(default=None)) -> dict:
    if not access_token:
        raise HTTPException(status_code=302, headers={"Location": "/panel/login"})
    try:
        payload = jwt.decode(access_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=302, headers={"Location": "/panel/login"})
        return {"username": username, "sub": username, "role": payload.get("role", "pending")}
    except JWTError:
        raise HTTPException(status_code=302, headers={"Location": "/panel/login"})


def require_admin(current_user: dict = Depends(get_current_user_from_cookie)) -> dict:
    """Dependency that restricts access to admin role only. Redirects others to dashboard."""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=302, headers={"Location": "/panel"})
    return current_user

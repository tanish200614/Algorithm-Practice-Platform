import os
import jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

DEV_SECRET = "algobattle-dev-secret-change-in-prod"

SECRET_KEY = os.environ.get("SECRET_KEY") or DEV_SECRET
ALGORITHM  = "HS256"
EXPIRE_DAYS = 30


def using_dev_secret() -> bool:
    """True when tokens are signed with the well-known development key."""
    return SECRET_KEY == DEV_SECRET

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(days=EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode(token: str) -> str:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired — please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _decode(creds.credentials)


def get_optional_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    if not creds:
        return None
    try:
        return _decode(creds.credentials)
    except HTTPException:
        return None


def token_from_query(token=None):
    """For WebSocket connections that pass token as ?token= query param."""
    if not token:
        return None
    try:
        return _decode(token)
    except HTTPException:
        return None

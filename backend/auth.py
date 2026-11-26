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


# Usernames minted by the GitHub login service (auth-service/) carry this
# prefix, and /register refuses it, so a password account can never squat on a
# GitHub user's name and inherit their rating.
GITHUB_PREFIX = "gh_"


def decode_claims(token: str) -> dict:
    """
    Verify a token and return its claims.

    Tokens come from two issuers sharing SECRET_KEY: this API (password
    logins) and the Spring Boot auth service (GitHub logins). The Spring tokens
    add a "roles" claim; tokens without one are plain users.
    """
    try:
        claims = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired — please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise HTTPException(status_code=401, detail="Invalid token")
    roles = claims.get("roles")
    claims["roles"] = [r for r in roles if isinstance(r, str)] if isinstance(roles, list) else ["USER"]
    return claims


def _decode(token: str) -> str:
    return decode_claims(token)["sub"]


def get_current_claims(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return decode_claims(creds.credentials)


def get_current_user(claims: dict = Depends(get_current_claims)) -> str:
    return claims["sub"]


def require_role(role: str):
    """Dependency factory: 403 unless the token carries `role`."""

    def check(claims: dict = Depends(get_current_claims)) -> str:
        if role not in claims["roles"]:
            raise HTTPException(status_code=403, detail=f"Requires the {role} role")
        return claims["sub"]

    return check


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

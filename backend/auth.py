"""
TaxFlow CRM — Authentication
JWT-based auth for staff (full access) and client portal (limited access).
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from loguru import logger

try:
    import bcrypt as _bcrypt
    _USE_BCRYPT = True
except ImportError:
    _USE_BCRYPT = False
    import hashlib, hmac, secrets

from .config import get_settings
from .models import (
    LoginRequest, TokenResponse, UserOut,
    ClientPortalLoginRequest, ClientPortalToken
)

# ─── Crypto ───────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a password using bcrypt (direct) or SHA-256 fallback."""
    if _USE_BCRYPT:
        salt = _bcrypt.gensalt(rounds=12)
        return _bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    else:
        # SHA-256 + salt fallback (development only)
        salt = secrets.token_hex(16)
        h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
        return f"sha256:{salt}:{h}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    if hashed.startswith('sha256:'):
        _, salt, h = hashed.split(':', 2)
        return hmac.compare_digest(
            hashlib.sha256(f"{salt}:{plain}".encode()).hexdigest(), h
        )
    # bcrypt verification
    try:
        return _bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


# ─── JWT Helpers ──────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    _settings = get_settings()
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=_settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, _settings.jwt_secret_key, algorithm=_settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    _settings = get_settings()
    try:
        payload = jwt.decode(
            token, _settings.jwt_secret_key, algorithms=[_settings.jwt_algorithm]
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── Bearer Scheme ────────────────────────────────────────────────────────────

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    """Dependency: returns the current authenticated staff user."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)

    if payload.get("type") != "staff":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff credentials required",
        )

    from .db import get_user_by_id
    user = await get_user_by_id(int(payload["sub"]))
    if not user or not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )
    return user


async def get_current_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency: requires admin role."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


async def get_current_client_or_staff(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    """
    Dependency: accepts either staff token or client portal token.
    Returns dict with 'type' field: 'staff' or 'client'.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    payload = decode_token(credentials.credentials)
    token_type = payload.get("type")

    if token_type == "staff":
        from .db import get_user_by_id
        user = await get_user_by_id(int(payload["sub"]))
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return {"type": "staff", **user}

    elif token_type == "client":
        from .db import get_client
        client = await get_client(int(payload["sub"]))
        if not client:
            raise HTTPException(status_code=401, detail="Client not found")
        return {"type": "client", **client}

    raise HTTPException(status_code=403, detail="Invalid token type")


# ─── Auth Router ──────────────────────────────────────────────────────────────

router = APIRouter(tags=["Authentication"])


@router.post("/auth/login", response_model=TokenResponse)
async def staff_login(request: LoginRequest):
    """Staff login — returns JWT for full CRM access."""
    from .db import get_user_by_email

    user = await get_user_by_email(request.email)
    if not user or not verify_password(request.password, user["password_hash"]):
        logger.warning(f"Failed login attempt for: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token({"sub": str(user["id"]), "type": "staff", "role": user["role"]})
    logger.info(f"Staff login: {request.email}")

    return TokenResponse(
        access_token=token,
        user=UserOut(
            id=user["id"],
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            created_at=datetime.fromisoformat(user["created_at"]),
            is_active=bool(user["is_active"]),
        )
    )


@router.post("/auth/portal/login", response_model=ClientPortalToken)
async def client_portal_login(request: ClientPortalLoginRequest):
    """Client portal login — returns JWT for client-only access."""
    from .db import get_client_by_email

    client = await get_client_by_email(request.email)
    if not client or not client.get("portal_password_hash"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or portal access not set up",
        )

    if not verify_password(request.password, client["portal_password_hash"]):
        logger.warning(f"Failed portal login for: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token(
        {"sub": str(client["id"]), "type": "client"},
        expires_delta=timedelta(hours=12)
    )
    logger.info(f"Client portal login: {request.email}")

    return ClientPortalToken(
        access_token=token,
        client_id=client["id"],
        client_name=client["full_name"],
    )


@router.post("/auth/refresh")
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """Refresh staff JWT token."""
    token = create_access_token(
        {"sub": str(current_user["id"]), "type": "staff", "role": current_user["role"]}
    )
    return {"access_token": token, "token_type": "bearer"}

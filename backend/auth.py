"""
TaxFlow CRM — Authentication
JWT-based auth for staff (full access) and client portal (limited access).
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from loguru import logger

from .config import get_settings
from .models import (
    LoginRequest, TokenResponse, UserOut,
    ClientPortalLoginRequest, ClientPortalToken
)

settings = get_settings()

# ─── Crypto ───────────────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ─── JWT Helpers ──────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
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
    user = await get_user_by_id(payload["sub"])
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
        user = await get_user_by_id(payload["sub"])
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return {"type": "staff", **user}

    elif token_type == "client":
        from .db import get_client
        client = await get_client(payload["sub"])
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

    token = create_access_token({"sub": user["id"], "type": "staff", "role": user["role"]})
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
        {"sub": client["id"], "type": "client"},
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
        {"sub": current_user["id"], "type": "staff", "role": current_user["role"]}
    )
    return {"access_token": token, "token_type": "bearer"}

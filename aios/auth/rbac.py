"""
AIOS RBAC Engine — Role-Based Access Control with JWT.
Roles: admin, operator, executive.
No external auth library — pure jose + passlib.
"""

from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from config import settings
import logging

logger = logging.getLogger("aios.auth")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Role Definitions ---

ROLE_PERMISSIONS = {
    "admin": {
        "read:incidents",
        "execute:low_risk",
        "execute:medium_risk",
        "execute:high_risk",
        "manage:users",
        "manage:knowledge",
        "read:executive",
        "read:observability",
    },
    "operator": {
        "read:incidents",
        "execute:low_risk",
        "execute:medium_risk",
        "read:observability",
        "manage:knowledge",
    },
    "executive": {
        "read:incidents",
        "read:executive",
    },
}

# --- Seeded Platform Users ---

SEED_USERS = [
    {"username": "admin", "password": "aios-admin-2026", "role": "admin", "display_name": "SRE Lead"},
    {"username": "engineer", "password": "aios-eng-2026", "role": "operator", "display_name": "On-Call Engineer"},
    {"username": "executive", "password": "aios-exec-2026", "role": "executive", "display_name": "VP Engineering"},
]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.JWT_EXPIRATION_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT token. Returns payload dict or None."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"JWT decode failed: {e}")
        return None


def has_permission(role: str, permission: str) -> bool:
    """Check if a role has a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())


def get_role_permissions(role: str) -> set[str]:
    """Get all permissions for a given role."""
    return ROLE_PERMISSIONS.get(role, set())

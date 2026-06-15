import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database import get_db
from models.database import User
from auth.rbac import verify_password, hash_password, create_access_token
from auth.dependencies import get_current_user, require_permission

router = APIRouter()
logger = logging.getLogger("aios.routes.auth")

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
    role: str
    display_name: str

class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = Field(description="Role: admin, operator, executive")
    display_name: str = ""

class UserCreateResponse(BaseModel):
    id: int
    username: str
    role: str
    display_name: str

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate a user and return a JWT access token."""
    try:
        stmt = select(User).where(User.username == request.username)
        res = await db.execute(stmt)
        user = res.scalars().first()
    except (SQLAlchemyError, OSError) as exc:
        logger.warning("Login failed because the database is unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please retry in a moment."
        ) from exc
    
    if not user or not verify_password(request.password, user.hashed_password) or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
        
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        username=user.username,
        role=user.role,
        display_name=user.display_name or user.username
    )

@router.post("/register", response_model=UserCreateResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_permission("manage:users"))
):
    """Register a new user account (Admin role required)."""
    try:
        # Check if user already exists
        stmt = select(User).where(User.username == request.username)
        res = await db.execute(stmt)
        existing = res.scalars().first()
    except (SQLAlchemyError, OSError) as exc:
        logger.warning("User registration failed because the database is unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please retry in a moment."
        ) from exc
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
        
    if request.role not in ["admin", "operator", "executive"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'admin', 'operator', or 'executive'"
        )
        
    hashed = hash_password(request.password)
    user = User(
        username=request.username,
        hashed_password=hashed,
        role=request.role,
        display_name=request.display_name
    )
    try:
        db.add(user)
        await db.commit()
        await db.refresh(user)
    except (SQLAlchemyError, OSError) as exc:
        logger.warning("User registration commit failed because the database is unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please retry in a moment."
        ) from exc
    
    return UserCreateResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        display_name=user.display_name or user.username
    )

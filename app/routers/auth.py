from datetime import timedelta
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.database import get_session
from app.models import User
from app.schemas import UserCreate, UserOut, Token
from app.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    verify_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# OAuth2 scheme for Swagger UI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# --- DEPENDENCIES ---

def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # SQLModel style query
    statement = select(User).where(User.email == email)
    user = session.exec(statement).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

def require_role(required_role: str) -> Callable:
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user
    return role_checker

# --- ENDPOINTS ---

@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, session: Session = Depends(get_session)):
    # Check if user exists
    statement = select(User).where(User.email == user_in.email)
    existing = session.exec(statement).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create new user
    db_user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role, # Allow setting role or default to USER
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    statement = select(User).where(User.email == form_data.username)
    user = session.exec(statement).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": user.email, "role": user.role},
        expires_delta=expires,
    )
    return {"access_token": token, "token_type": "bearer"}

@router.get("/users/me", response_model=UserOut)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/admin/ping")
def admin_ping(current_admin: User = Depends(require_role("ADMIN"))):
    return {"ok": True, "admin": current_admin.email}
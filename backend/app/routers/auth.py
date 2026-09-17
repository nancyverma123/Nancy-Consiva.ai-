import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.security import create_access_token, hash_password, verify_password
from app.services.rate_limit import client_ip, enforce, enforce_guest_signup

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        display_name=payload.display_name,
        is_guest=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token, user_id=user.id, is_guest=False)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    enforce(f"login:{client_ip(request)}", 10, 300, "Too many sign-in attempts. Please wait a few minutes.")
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token, user_id=user.id, is_guest=False)


@router.post("/guest", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def guest_login(request: Request, db: Session = Depends(get_db)):
    """Issue a scoped JWT for an anonymous guest user, so the widget works without signup."""
    # New guest sessions reset per-user limits, so cap how many one network can create.
    enforce_guest_signup(client_ip(request))
    user = User(email=f"guest-{uuid.uuid4().hex[:12]}@guest.consiva.local", is_guest=True)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.id, extra_claims={"guest": True})
    return TokenResponse(access_token=token, user_id=user.id, is_guest=True)

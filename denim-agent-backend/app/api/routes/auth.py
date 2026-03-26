from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.core.database import engine
from app.core import security
from app.api.deps import get_db, get_current_user
from app.core.config import settings
from app.models.domain import User
from app.models.schemas import Token, UserProfileUpdate, UserProfileResponse

router = APIRouter()

@router.post("/login/access-token", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    user = db.exec(select(User).where(User.email == form_data.username)).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }

@router.get("/me", response_model=UserProfileResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user)
) -> Any:
    return current_user

@router.put("/me", response_model=UserProfileResponse)
def update_current_user_profile(
    user_update: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    if user_update.email is not None and user_update.email != current_user.email:
        # Check if email is already taken
        existing_user = db.exec(select(User).where(User.email == user_update.email)).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        current_user.email = user_update.email
    
    if user_update.first_name is not None:
        current_user.first_name = user_update.first_name
        
    if user_update.last_name is not None:
        current_user.last_name = user_update.last_name

    if user_update.new_password is not None:
        if user_update.current_password is None:
            raise HTTPException(status_code=400, detail="Current password required to set a new password")
        if not security.verify_password(user_update.current_password, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="Incorrect current password")
        current_user.hashed_password = security.get_password_hash(user_update.new_password)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user

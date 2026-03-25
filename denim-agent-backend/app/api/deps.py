from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlmodel import Session

from app.core.database import engine
from app.core.config import settings
from app.models.domain import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login/access-token"
)

def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = payload.get("sub")
        if token_data is None:
            raise credentials_exception
    except (JWTError, ValidationError):
        raise credentials_exception
    
    user = db.get(User, token_data)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return user

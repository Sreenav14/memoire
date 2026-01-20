import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from sqlalchemy import select

from .deps import get_db
from .models import User

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db:Session = Depends(get_db),
)-> User:
    token = credentials.credentials
    secret = os.getenv("JWT_SECRET")
    alg = os.getenv("JWT_ALG","HS256")
    
    if not secret:
        raise RuntimeError("JWT_SECRET is not set")
    
    try: 
        payload = jwt.decode(token, secret, algorithms=[alg])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    
    user = db.execute(select(User).where(User.id==user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user
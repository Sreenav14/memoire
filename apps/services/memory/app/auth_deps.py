import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

credentials = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(credentials))-> str:
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
    print("Memory auth created")
    return user_id
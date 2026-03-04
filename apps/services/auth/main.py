import os
from fastapi import FastAPI, HTTPException, Depends
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .deps import get_db
from .models import User, Space, UserSpace, UserPassword
from .schema.schemas import SignupRequest, LoginRequest
from .auth import hash_password, create_access_token, verify_password
from .auth_deps import get_current_user

load_dotenv()
app = FastAPI(title="MEMOIRE API", version="0.1.0")

@app.get("/health")
def health():
    return {"status": "ok", "service": "memoire-api"}

@app.get("/me")
def me(current_user: User = Depends(get_current_user), db:Session = Depends(get_db)):
    
    rows = db.execute(
        select(Space.id, Space.name, UserSpace.role, UserSpace.created_at)
        .join(UserSpace, UserSpace.space_id==Space.id)
        .where(UserSpace.user_id==current_user.id)
        .order_by(UserSpace.created_at.asc())
        ).all()
    
    spaces = [
        {"id": str( r[0]), "name": r[1], "role": r[2], "created_at": r[3]}
        for r in rows
    ]
    
    return {
        "user" : {
            "id": str(current_user.id),
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "email": current_user.email,
            "email_verified": current_user.email_verified,
            "created_at": current_user.created_at,
        },
        "spaces": spaces,
    }

@app.get("/spaces")
def list_spaces(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Space.id, Space.name, UserSpace.role, UserSpace.created_at)
        .join(UserSpace, UserSpace.space_id == Space.id)
        .where(UserSpace.user_id == current_user.id)
        .order_by(UserSpace.created_at.asc())
    ).all()

    return [
        {"id": str(r[0]), "name": r[1], "role": r[2], "created_at": r[3]}
        for r in rows
    ]
    
@app.post("/auth/signup")
def signup(payload: SignupRequest, db:Session = Depends(get_db)):
    email = payload.email.lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    # 1 create User
    user = User(
        first_name = payload.first_name,
        last_name = payload.last_name,
        email = email,
        email_verified = False,
    )
    
    try:
        db.add(user)
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # 2 create password
    
    pw = UserPassword(
        user_id = user.id,
        password_hash = hash_password(payload.password),
    )
    db.add(pw)
    
    # 3. Create default space + membership
    space = Space(
        name = "Personal",
        owner_user_id = user.id
    )
    db.add(space)
    db.flush()
    
    membership = UserSpace(user_id = user.id, space_id = space.id, role = "owner")
    db.add(membership)
    
    # 4 commit transaction
    db.commit()
    
    # 5 return access token
    return {
        "access_token": create_access_token(str(user.id)),
        "token_type": "Bearer",
        "user":{
            "id":str(user.id),
            "first_name":user.first_name,
            "last_name":user.last_name,
            "email":user.email,
        },
        "default_space":{"id":str(space.id), "name":space.name},
    }
    
@app.post("/auth/login")
def login(payload: LoginRequest, db:Session = Depends(get_db)):
    email = payload.email.lower()
    
    user = db.execute(select(User).where(User.email==email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    pw = db.execute(select(UserPassword).where(UserPassword.user_id==user.id)).scalar_one_or_none()
    if not pw:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not verify_password(payload.password, pw.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_access_token(str(user.id))
    return {
        "access_token": token,
        "token_type": "Bearer"
    }

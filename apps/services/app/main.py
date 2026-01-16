import os
from fastapi import FastAPI, HTTPException, Depends
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .Database.deps import get_db
from .Database.models import User, Space, UserSpace
from .schema.schemas import SignupRequest
from .auth.auth import hash_password, create_access_token
from .Database.models import User, UserPassword, Space, UserSpace

load_dotenv()
app = FastAPI(title ="MEMORIE API", version = "0.1.0")

@app.get("/health")
def health():
    return {"status": "ok", "service": "memoire-api"}

@app.get("/me")
def me(db:Session = Depends(get_db)):
    """ 
    Dev-only for now
    """
    
    dev_email = os.getenv("DEV_EMAIL","dev@memoire.local").lower()
    user = db.execute(select(User).where(User.email==dev_email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    rows = db.execute(
        select(Space.id, Space.name, UserSpace.role, Space.created_at)
        .join(UserSpace, UserSpace.user_id==user.id)
        .where(UserSpace.user_id==user.id)
        .order_by(Space.created_at.desc())
    ).all()

    spaces = [
        {"id": r[0], "name":r[1], "role":r[2], "created_at":r[3]}
        for r in rows
    ]
    
    return {
        "user" : {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email":user.email,
            "email_verified":user.email_verified,
            "created_at":user.created_at,
        },
        "spaces": spaces,
    }
    
@app.post("/signup")
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
    
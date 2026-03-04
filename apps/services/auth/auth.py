import os
from datetime import datetime, timedelta, timezone
from jose import jwt
from bcrypt import gensalt, hashpw, checkpw


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    salt = gensalt()
    return hashpw(password_bytes, salt).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    password_bytes = password.encode("utf-8")
    hashed_password_bytes = hashed_password.encode("utf-8")
    return checkpw(password_bytes, hashed_password_bytes)


def create_access_token(subject: str) -> str:
    secret = os.getenv("JWT_SECRET")
    alg = os.getenv("JWT_ALG", "HS256")
    expire_minutes = int(os.getenv("JWT_EXPIRES_MINUTES", "120"))

    if not secret:
        raise RuntimeError("JWT_SECRET is not set")

    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=expire_minutes)

    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    return jwt.encode(payload, secret, algorithm=alg)
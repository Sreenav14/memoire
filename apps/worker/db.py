import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv, find_dotenv

load_dotenv()

class Base(DeclarativeBase):
    pass

db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise RuntimeError("DATABASE_URL is not set")

engine = create_engine(db_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
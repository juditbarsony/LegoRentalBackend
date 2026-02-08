import os
from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine, Session
from typing import Generator

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/dbname")

# SQLModel uses SQLAlchemy under the hood
engine = create_engine(DATABASE_URL, echo=True)

def create_db_and_tables():
    # Import models here to ensure they are registered with SQLModel.metadata
    from app import models  # noqa: F401
    SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

# Alias for backward compatibility if needed
def get_db() -> Generator[Session, None, None]:
    yield from get_session()
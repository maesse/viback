from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session
from models import Base
from typing import Generator
from config import get_config
import os

def init_db() -> Engine:
    """Initialize database connection and create tables"""
    config = get_config()
    db_url = config['DEFAULT']['database_url']
    
    # For SQLite, ensure directory exists
    if db_url.startswith('sqlite:///'):
        db_path = db_url.split('sqlite:///')[1]
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return engine

def get_session_factory(engine: Engine) -> sessionmaker:
    """Create and return a session factory"""
    return sessionmaker(bind=engine)

# Initialize database on import
engine = init_db()
SessionLocal = get_session_factory(engine)

def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

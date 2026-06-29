from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from config import Config

engine = create_engine(Config.DATABASE_URL, echo=False)
SessionLocal = scoped_session(sessionmaker(bind=engine))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models import Base
    Base.metadata.create_all(bind=engine)

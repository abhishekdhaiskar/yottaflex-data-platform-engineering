import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Explicitly default to the yottaflex container credentials
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://yottaflex:local_dev_password@localhost:5432/yottaflex"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
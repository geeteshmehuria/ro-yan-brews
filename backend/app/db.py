import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./royan.db")
# Render's Postgres URLs sometimes use the legacy scheme
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def add_missing_columns(bind) -> None:
    """create_all() never alters existing tables, so add any *nullable* model column
    the database doesn't have yet (our whole "migration" story — see CLAUDE.md)."""
    insp = inspect(bind)
    with bind.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in have and col.nullable:
                    conn.execute(text(
                        f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(bind.dialect)}"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

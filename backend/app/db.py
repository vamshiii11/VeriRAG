from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import resolve_backend_path, settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
database_url = make_url(settings.database_url)
if database_url.drivername.startswith("sqlite") and database_url.database not in (None, "", ":memory:"):
    database_path = resolve_backend_path(database_url.database)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = database_url.set(database=str(database_path))
engine = create_engine(database_url.render_as_string(hide_password=False), connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

def upgrade_sqlite_schema():
    """Add fields introduced after the initial prototype without deleting data."""
    if engine.dialect.name != "sqlite":
        Base.metadata.create_all(bind=engine)
        with engine.begin() as connection:
            columns={column["name"] for column in inspect(connection).get_columns("documents")}
            if "content_hash" not in columns:
                connection.execute(text("ALTER TABLE documents ADD COLUMN content_hash VARCHAR(64)"))
            from .models import Document, Query
            for table in (Document.__table__,Query.__table__):
                for index in table.indexes:
                    index.create(bind=connection,checkfirst=True)
        return
    Base.metadata.create_all(bind=engine)
    additions = {
        "documents": {
            "metadata_source": "VARCHAR DEFAULT 'manual_or_inferred'",
            "metadata_uncertain": "BOOLEAN DEFAULT 0",
            "supersedes_document_id": "VARCHAR",
            "content_hash": "VARCHAR(64)",
        },
        "queries": {
            "trust_details": "JSON",
            "temporal_summary": "JSON",
        },
        "evidence": {"temporal_status": "VARCHAR DEFAULT 'UNRESOLVED'"},
        "claim_evidence": {"temporal_status": "VARCHAR DEFAULT 'UNRESOLVED'"},
    }
    with engine.begin() as connection:
        inspector = inspect(connection)
        for table, columns in additions.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, definition in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_owner_content_hash ON documents (owner_id, content_hash)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_owner_created_at ON documents (owner_id, created_at)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_queries_owner_created_at ON queries (owner_id, created_at)"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

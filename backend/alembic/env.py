from alembic import context
from app.db import Base
from app import models
from app.config import settings
target_metadata=Base.metadata
def run_migrations_online():
    from sqlalchemy import engine_from_config,pool
    cfg=context.config
    cfg.set_main_option("sqlalchemy.url",settings.database_url)
    with engine_from_config(cfg.get_section(cfg.config_ini_section),prefix="sqlalchemy.",poolclass=pool.NullPool).connect() as connection:
        context.configure(connection=connection,target_metadata=target_metadata,compare_type=True)
        with context.begin_transaction(): context.run_migrations()
run_migrations_online()

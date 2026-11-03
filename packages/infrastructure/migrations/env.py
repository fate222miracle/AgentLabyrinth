"""Run versioned migrations on an explicitly supplied connection."""

from alembic import context

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("An explicit database connection is required")

context.configure(connection=connection)
with context.begin_transaction():
    context.run_migrations()

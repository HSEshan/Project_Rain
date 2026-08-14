from libs.db import create_engine, create_session_factory
from src.core.config import settings

# Engine settings and the ORM models both live in `libs.db`; this service and
# rest_api must not drift apart on either. ws_gateway does not own the schema —
# rest_api runs the Alembic migrations.
engine = create_engine(settings.ASYNC_DB_URL)
AsyncSessionLocal = create_session_factory(engine)

FROM python:3.12.4-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y build-essential

# Copy libs and install. The `db` extra pulls SQLAlchemy/asyncpg/alembic —
# rest_api owns the schema and imports the shared models from libs.db.
COPY ./libs /app/libs
RUN pip install --no-cache-dir "/app/libs[db]"

# Copy rest_api code
COPY ./rest_api /app

# Install rest_api dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run rest_api
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
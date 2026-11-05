FROM python:3.12.4-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y build-essential

# Copy libs and install as package. The `db` extra gives this service the same
# ORM models rest_api uses; it reads/writes the same tables.
COPY ./libs /app/libs
RUN pip install --no-cache-dir "/app/libs[db]"

# Copy ws_gateway code
COPY ./ws_gateway /app

# Install ws_gateway dependencies
RUN pip install --no-cache-dir -r requirements.txt

# --ws-max-size: the largest honest frame is a 4000 character message, escaped.
# uvicorn's default is 16 MB, read and parsed before anything can look at it.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--ws-max-size", "65536"]
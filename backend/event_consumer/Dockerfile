FROM python:3.12.4-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y build-essential

# Copy libs and install as package
COPY ./libs /app/libs
RUN pip install --no-cache-dir /app/libs

# Copy event_consumer code
COPY ./event_consumer /app

# Install event_consumer dependencies
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
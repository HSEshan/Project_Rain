FROM python:3.12.4-slim

# Install required packages
RUN apt-get update && apt-get install -y \
  curl git unzip tar libnss3 libx11-xcb1 libxcomposite1 libxdamage1 \
  libxrandr2 libgbm1 libasound2 libatk-bridge2.0-0 libgtk-3-0 \
  libpangocairo-1.0-0 libcairo2 libpango-1.0-0 fonts-liberation xvfb \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m docker && mkdir -p /home/docker/actions-runner && chown -R docker:docker /home/docker
# Switch to user
USER docker
WORKDIR /home/docker/actions-runner

# Copy setup script
COPY --chown=docker:docker setup.sh /home/docker/setup.sh
RUN chmod +x /home/docker/setup.sh

ENTRYPOINT ["/home/docker/setup.sh"]

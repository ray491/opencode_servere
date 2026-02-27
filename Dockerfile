FROM node:20-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    MCP_HEADLESS=false \
    MCP_VIDEO_DIR=/app/recordings

RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update -o Acquire::Retries=3 -o Acquire::https::Timeout=30 \
    && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    chromium \
    ffmpeg \
    xvfb \
    openssh-server \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir mcp playwright --break-system-packages
RUN npm i -g opencode-ai

WORKDIR /app

COPY mcp_server.py /app/mcp_server.py
COPY opencode.json /app/opencode.json

RUN mkdir -p /root/.config/opencode \
    && cp /app/opencode.json /root/.config/opencode/opencode.json

RUN mkdir -p /app/recordings

# Configure SSH server
RUN mkdir /var/run/sshd \
    && echo "root:rootpass" | chpasswd \
    && sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config \
    && sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Entrypoint script to start sshd + opencode
RUN printf '#!/bin/bash\n/usr/sbin/sshd\nexec xvfb-run -a opencode serve --hostname 0.0.0.0\n' > /entrypoint.sh \
    && chmod +x /entrypoint.sh

EXPOSE 4096
EXPOSE 1455
EXPOSE 22

CMD ["/entrypoint.sh"]

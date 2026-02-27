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
    vsftpd \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir mcp playwright --break-system-packages
RUN npm i -g opencode-ai

WORKDIR /app

COPY mcp_server.py /app/mcp_server.py
COPY opencode.json /app/opencode.json

RUN mkdir -p /root/.config/opencode \
    && cp /app/opencode.json /root/.config/opencode/opencode.json

RUN mkdir -p /app/recordings

# Configure vsftpd
RUN echo "listen=YES" > /etc/vsftpd.conf \
    && echo "listen_ipv6=NO" >> /etc/vsftpd.conf \
    && echo "anonymous_enable=NO" >> /etc/vsftpd.conf \
    && echo "local_enable=YES" >> /etc/vsftpd.conf \
    && echo "write_enable=YES" >> /etc/vsftpd.conf \
    && echo "local_umask=022" >> /etc/vsftpd.conf \
    && echo "chroot_local_user=NO" >> /etc/vsftpd.conf \
    && echo "allow_writeable_chroot=YES" >> /etc/vsftpd.conf \
    && echo "pasv_enable=YES" >> /etc/vsftpd.conf \
    && echo "pasv_min_port=21000" >> /etc/vsftpd.conf \
    && echo "pasv_max_port=21010" >> /etc/vsftpd.conf \
    && echo "seccomp_sandbox=NO" >> /etc/vsftpd.conf

# Create FTP user (user: ftpuser, password: ftppass — change as needed)
RUN useradd -m ftpuser \
    && echo "ftpuser:ftppass" | chpasswd

# Entrypoint script to start vsftpd + opencode
RUN printf '#!/bin/bash\nvsftpd /etc/vsftpd.conf &\nexec xvfb-run -a opencode serve --hostname 0.0.0.0\n' > /entrypoint.sh \
    && chmod +x /entrypoint.sh

EXPOSE 4096
EXPOSE 1455
EXPOSE 21
EXPOSE 21000-21010

CMD ["/entrypoint.sh"]

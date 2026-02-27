# opencode-browser-mcp

A Docker container running [opencode](https://opencode.ai) with a browser automation MCP server powered by Playwright. Records all browser sessions as mp4 and exposes them via a simple HTTP API.

## What's inside

- **opencode** — AI coding agent, served on port `4096`
- **Browser MCP server** — Playwright-based browser automation with anti-bot spoofing, session recording, and sandboxed network access
- **HTTP API** — retrieve or delete session recordings on port `80`
- **SFTP access** — browse the container filesystem via SSH on port `22`
- **Xvfb** — virtual display so the browser runs headlessly inside the container

## Requirements

- Docker
- `opencode.json` — your opencode config file
- `mcp_server.py` — the browser MCP server (included)

## Getting started

### 1. Build

```bash
docker build -t opencode-browser-mcp .
```

### 2. Run

```bash
docker run -d \
  -p 4096:4096 \
  -p 80:80 \
  -p 22:22 \
  --name opencode \
  opencode-browser-mcp
```

### 3. Connect to opencode

Open `http://localhost:4096` in your browser.

## SFTP access

Connect with any SFTP client (FileZilla, WinSCP, etc.):

| Field    | Value       |
|----------|-------------|
| Protocol | SFTP        |
| Host     | `localhost` |
| Port     | `22`        |
| User     | `root`      |
| Password | `rootpass`  |

> **Change the default password** before exposing this container publicly. Edit the `echo "root:rootpass" | chpasswd` line in the Dockerfile.

## Recording API

Browser sessions are automatically recorded and converted to mp4 after the browser closes. Recordings are stored in `/app/recordings` inside the container.

### Get latest recording

```
GET http://localhost/recording
```

Returns a JSON response with the latest mp4 encoded as base64:

```json
{
  "filename": "recording_20260101_120000.mp4",
  "size_bytes": 2345678,
  "base64": "AAAA..."
}
```

Save it locally:

```bash
curl http://localhost/recording | python3 -c "
import sys, json, base64
data = json.load(sys.stdin)
open(data['filename'], 'wb').write(base64.b64decode(data['base64']))
print('Saved:', data['filename'])
"
```

### Delete all recordings

```
DELETE http://localhost/recordings
```

```json
{
  "deleted": ["file1.mp4", "file2.mp4"],
  "count": 2
}
```

## Environment variables

| Variable        | Default            | Description                              |
|-----------------|--------------------|------------------------------------------|
| `MCP_HEADLESS`  | `false`            | Run browser in headless mode             |
| `MCP_VIDEO_DIR` | `/app/recordings`  | Directory where recordings are saved     |
| `MCP_HTTP_PORT` | `80`               | Port for the recording HTTP API          |

## Files

| File            | Description                          |
|-----------------|--------------------------------------|
| `Dockerfile`    | Container definition                 |
| `mcp_server.py` | Browser MCP server with HTTP API     |
| `opencode.json` | opencode configuration (you provide) |

## Notes

- Playwright records sessions as `.webm` internally (a CDP limitation). The server automatically converts all recordings to `.mp4` using ffmpeg on browser close. Any leftover `.webm` files are caught by a failsafe sweep.
- The browser blocks requests to `localhost`, `127.x`, `192.168.x`, `10.x`, and `file://` URLs as a sandbox policy.
- Real Chrome is used if found at common paths to reduce bot detection. Falls back to Playwright's bundled Chromium otherwise.

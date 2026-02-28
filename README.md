# opencode-browser-mcp
A Docker container running [opencode](https://opencode.ai) with a browser automation MCP server powered by Playwright. Records all browser sessions as webm and exposes them via a simple HTTP API.

## What's inside
- **opencode** — AI coding agent, served on port `4096`
- **Browser MCP server** — Playwright-based browser automation with anti-bot spoofing, session recording, and sandboxed network access
- **HTTP API** — list, download, or delete session recordings on port `80`
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
Browser sessions are automatically recorded as `.webm` files and stored in `/app/recordings` inside the container.

### List all recordings
```
GET http://localhost/recordings
```
Returns a list of all recording files, sorted newest first:
```json
{
  "recordings": [
    { "filename": "session-abc123.webm", "size_bytes": 2345678 },
    { "filename": "session-def456.webm", "size_bytes": 1234567 }
  ],
  "count": 2
}
```

### Download a recording
```
GET http://localhost/recording/download/{filename}
```
Returns the named file encoded as base64:
```json
{
  "filename": "session-abc123.webm",
  "size_bytes": 2345678,
  "base64": "AAAA..."
}
```

Save it locally:
```bash
curl http://localhost/recording/download/session-abc123.webm | python3 -c "
import sys, json, base64
data = json.load(sys.stdin)
open(data['filename'], 'wb').write(base64.b64decode(data['base64']))
print('Saved:', data['filename'])
"
```

Or to download the newest recording in one shot, list first then download:
```bash
FILENAME=$(curl -s http://localhost/recordings | python3 -c "import sys,json; print(json.load(sys.stdin)['recordings'][0]['filename'])")
curl http://localhost/recording/download/$FILENAME | python3 -c "
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
  "deleted": ["session-abc123.webm", "session-def456.webm"],
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
- Playwright records sessions as `.webm` files (a CDP limitation). Recordings are saved as-is — no transcoding required.
- The browser blocks requests to `localhost`, `127.x`, `192.168.x`, `10.x`, and `file://` URLs as a sandbox policy.
- Real Chrome is used if found at common paths to reduce bot detection. Falls back to Playwright's bundled Chromium otherwise.

# opencode-browser-mcp + Odoo MCP

This project combines:
- **opencode** with a Playwright browser MCP server and recording API
- **Odoo MCP** (module + Python MCP server) for full CRUD access with granular permissions

## What's inside
- **opencode** — AI coding agent, served on port `4096`
- **Browser MCP server** — Playwright-based browser automation with anti-bot spoofing, session recording, and sandboxed network access
- **HTTP API** — list, download, or delete session recordings on port `80`
- **SFTP access** — browse the container filesystem via SSH on port `22`
- **Xvfb** — virtual display so the browser runs headlessly inside the container
- **Odoo MCP module** — JSON endpoints with CRUD and per-model permissions
- **Odoo MCP server** — Python MCP server that calls the Odoo module endpoints

## Requirements
- Docker
- `opencode.json` — your opencode config file
- `mcp_server.py` — the browser MCP server (included)
- Odoo instance with addons path access

## Getting started (opencode + browser MCP)

### 1. Build
```bash
docker run -d \
docker build -t opencode-browser-mcp .
```

### 2. Run
```bash
  -p 4096:4096 \
  -p 80:80 \
  -p 22:22 \
  --name opencode \
  opencode-browser-mcp
```

### 3. Connect to opencode
Open `http://localhost:4096` in your browser.

## Odoo MCP (module + Python server)

### 1) Install the Odoo module

1. Copy `odoo_mcp/odoo_module/odoo_mcp_module` into your Odoo addons path.
2. Update your Apps list and install **MCP Read API**.
3. (Recommended) Set a token in Odoo:
   - Settings -> Technical -> Parameters -> System Parameters
   - Key: `mcp.token`
   - Value: `<your-secret>`
4. Create per-model MCP permissions in Odoo:
   - Settings -> MCP -> Access
   - Enable the models and operations you want to allow
   - Default is deny for any model not listed
5. Create an Odoo API key for the user that should be used by MCP

System parameters (optional):
- `mcp.require_auth` (default 1) requires login+api_key on every request
- `mcp.default_deny` (default 1) denies any model not listed in MCP Access

### 2) Run the Python MCP server

```bash
cd odoo_mcp/python_server
python -m pip install -r requirements.txt
set ODOO_BASE_URL=http://localhost:8069
set ODOO_DB=your_db_name
set ODOO_MCP_TOKEN=your-secret
set ODOO_LOGIN=your_odoo_login
set ODOO_API_KEY=your_odoo_api_key
python server.py
```

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
- The Odoo module respects normal record rules and access rights.
- If `mcp.token` is set, requests must include the token.
- The Python MCP server forwards token/login/api_key automatically.

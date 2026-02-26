# Browser MCP Server (Python)

Sandboxed browser MCP server that prefers your real Chrome to reduce bot detection and CAPTCHAs, and falls back to Playwright Chromium when Chrome is not found.

## Features
- Uses installed Chrome when available (Windows paths preconfigured)
- Falls back to Playwright Chromium
- Blocks local/file URLs for safety
- Persistent sandbox profile in temp directory
- MCP tools for navigation, search, clicking, typing, scrolling, text extraction, and screenshots

## Requirements
- Python 3.10+
- Playwright + Chromium

## Install
```bash
pip install mcp playwright
playwright install chromium
```

## Run locally
```bash
python3 mcp_server.py
```

## Docker
```bash
docker build -t browser-mcp .
docker run --rm -p 4096:4096 browser-mcp
```

## OpenCode config
This repo includes `opencode.json` for a local MCP server config.
```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "ai_browser_mcp_server": {
      "type": "local",
      "command": ["python3", "/app/mcp_server.py"]
    }
  }
}
```

## Example MCP flow
```json
{
  "tool": "navigate",
  "arguments": { "url": "https://example.com" }
}
```

```json
{
  "content": [
    { "type": "text", "text": "Navigated to: https://example.com\nTitle: Example Domain" },
    { "type": "image", "mimeType": "image/jpeg", "data": "<base64>" }
  ]
}
```

## Tools
- `navigate` { url }
- `search` { query }
- `click` { selector | text }
- `type_text` { selector, text, clear_first? }
- `scroll` { direction, amount }
- `get_text` { selector?, max_length? }
- `screenshot` {}
- `go_back` {}
- `get_url` {}
- `wait_for` { selector | ms }
- `close_browser` {}

## Notes
- Local and file URLs are blocked by default.
- Chrome detection paths are defined in `mcp_server.py` and can be extended for your environment.
- The sandbox profile is stored under your temp directory as `browser-mcp-sandbox`.

## Troubleshooting
- If Chrome is not found, the server will log a fallback to Playwright Chromium.
- If Playwright is missing, install it and run `playwright install chromium`.

## Files
- `mcp_server.py`: MCP server implementation
- `opencode.json`: OpenCode MCP config
- `Dockerfile`: container build for the server

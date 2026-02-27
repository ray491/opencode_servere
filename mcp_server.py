"""
Browser MCP Server (Python) — Windows + Anti-CAPTCHA
──────────────────────────────────────────────────────
Uses your REAL installed Chrome to avoid bot detection / CAPTCHAs.
Falls back to Playwright's bundled Chromium if Chrome isn't found.
"""

import asyncio
import base64
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from datetime import datetime
from pathlib import Path

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import CallToolResult, ImageContent, TextContent, Tool
except ImportError:
    print("ERROR: Run:  pip install mcp playwright", file=sys.stderr)
    sys.exit(1)

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: Run:  pip install playwright && playwright install chromium", file=sys.stderr)
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
SANDBOX_PROFILE = Path(tempfile.gettempdir()) / "browser-mcp-sandbox"
HEADLESS = os.getenv("MCP_HEADLESS", "false").strip().lower() in {"1", "true", "yes", "on"}
RECORD_VIDEO_DIR = Path(os.getenv("MCP_VIDEO_DIR", "/app/recordings"))

# Point to your REAL Chrome — avoids bot fingerprints that trigger CAPTCHAs.
# Set to None to use Playwright's bundled Chromium instead.
REAL_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Users\main\AppData\Local\Google\Chrome\Application\chrome.exe",
    r"/usr/bin/chromium",
    r"/usr/bin/chromium-browser",
]

def find_chrome() -> str | None:
    for p in REAL_CHROME_PATHS:
        if Path(p).exists():
            print(f"[browser-mcp] Using real Chrome: {p}", file=sys.stderr)
            return p
    print("[browser-mcp] Real Chrome not found, falling back to Playwright Chromium", file=sys.stderr)
    return None

CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    # ── Anti-bot detection ──────────────────────────────────────────────────
    "--disable-blink-features=AutomationControlled",  # hides navigator.webdriver flag
    "--disable-infobars",
    "--disable-extensions",
    "--disable-sync",
    "--no-first-run",
    "--disable-background-networking",
    "--disable-default-apps",
    "--disable-translate",
    "--metrics-recording-only",
    "--window-size=1280,800",
]

BLOCKED = [
    re.compile(r"^https?://localhost"),
    re.compile(r"^https?://127\."),
    re.compile(r"^https?://192\.168\."),
    re.compile(r"^https?://10\."),
    re.compile(r"^https?://172\.(1[6-9]|2\d|3[01])\."),
    re.compile(r"^file://"),
]

# ── State ─────────────────────────────────────────────────────────────────────
_pw = None
_context = None
_page = None


async def get_page():
    global _pw, _context, _page
    if _page is None:
        _pw = await async_playwright().start()
        SANDBOX_PROFILE.mkdir(parents=True, exist_ok=True)
        RECORD_VIDEO_DIR.mkdir(parents=True, exist_ok=True)

        chrome_path = find_chrome()

        _context = await _pw.chromium.launch_persistent_context(
            str(SANDBOX_PROFILE),
            headless=HEADLESS,
            executable_path=chrome_path,   # None = use bundled Chromium
            args=CHROMIUM_ARGS,
            viewport={"width": 1280, "height": 800},
            accept_downloads=False,
            record_video_dir=str(RECORD_VIDEO_DIR),
            record_video_size={"width": 1280, "height": 800},
            # Spoof a real user agent
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        _page = await _context.new_page()

        # Remove the webdriver property that sites check for bots
        await _page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            // Spoof plugins to look like a real browser
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            // Spoof languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
        """)

        async def block_local(route):
            if any(p.match(route.request.url) for p in BLOCKED):
                print(f"[SANDBOX BLOCKED] {route.request.url}", file=sys.stderr)
                await route.abort()
            else:
                await route.continue_()

        await _page.route("**/*", block_local)

        def close_popups(new_page):
            if new_page is not _page:
                asyncio.ensure_future(new_page.close())

        _context.on("page", close_popups)

    return _page


def _mp4_path_from_webm(webm_path: Path) -> Path:
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base = webm_path.stem or f"mcp_recording_{stamp}"
    return webm_path.with_name(f"{base}_{stamp}.mp4")


def _transcode_to_mp4(webm_path: Path) -> Path:
    """Convert webm to mp4. Always required — raises RuntimeError if ffmpeg is missing or fails."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found in PATH — cannot convert recording to mp4")

    mp4_path = _mp4_path_from_webm(webm_path)
    cmd = [
        ffmpeg,
        "-y",
        "-i", str(webm_path),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        str(mp4_path),
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg conversion failed (exit {result.returncode}):\n"
            + result.stderr.decode(errors="replace")
        )

    webm_path.unlink(missing_ok=True)
    print(f"[browser-mcp] Recording saved: {mp4_path}", file=sys.stderr)
    return mp4_path


async def close_all():
    global _pw, _context, _page
    video_path = None
    if _page and _page.video:
        try:
            await _page.close()
            video_path = Path(await _page.video.path())
        except Exception as e:
            print(f"[browser-mcp] Video finalize failed: {type(e).__name__}: {e}", file=sys.stderr)
    if _context:
        await _context.close()
    if _pw:
        await _pw.stop()
    _pw = _context = _page = None
    if video_path and video_path.exists():
        try:
            _transcode_to_mp4(video_path)
        except RuntimeError as e:
            print(f"[browser-mcp] ERROR: {e}", file=sys.stderr)
            sys.exit(1)


async def snap() -> str:
    p = await get_page()
    buf = await p.screenshot(type="jpeg", quality=65, full_page=False)
    return base64.b64encode(buf).decode()


def ok(text: str, img: str | None = None) -> CallToolResult:
    content = [TextContent(type="text", text=text)]
    if img:
        content.append(ImageContent(type="image", data=img, mimeType="image/jpeg"))
    return CallToolResult(content=content)


def err(msg: str) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=f"Error: {msg}")],
        isError=True,
    )


# ── MCP Server ────────────────────────────────────────────────────────────────
app = Server("browser-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="navigate",
             description="Go to a URL in the sandboxed browser.",
             inputSchema={"type": "object",
                          "properties": {"url": {"type": "string"}},
                          "required": ["url"]}),
        Tool(name="search",
             description="Google search — opens results page.",
             inputSchema={"type": "object",
                          "properties": {"query": {"type": "string"}},
                          "required": ["query"]}),
        Tool(name="click",
             description="Click an element. Use 'selector' (CSS) or 'text' (visible label).",
             inputSchema={"type": "object",
                          "properties": {
                              "selector": {"type": "string"},
                              "text": {"type": "string"},
                          }}),
        Tool(name="type_text",
             description="Type into an input field.",
             inputSchema={"type": "object",
                          "properties": {
                              "selector": {"type": "string"},
                              "text": {"type": "string"},
                              "clear_first": {"type": "boolean", "default": True},
                          },
                          "required": ["selector", "text"]}),
        Tool(name="scroll",
             description="Scroll the page up or down.",
             inputSchema={"type": "object",
                          "properties": {
                              "direction": {"type": "string", "enum": ["up", "down"]},
                              "amount": {"type": "number"},
                          }}),
        Tool(name="get_text",
             description="Get visible text of page or a CSS element.",
             inputSchema={"type": "object",
                          "properties": {
                              "selector": {"type": "string"},
                              "max_length": {"type": "number"},
                          }}),
        Tool(name="screenshot",
             description="Capture the current viewport as a JPEG image.",
             inputSchema={"type": "object", "properties": {}}),
        Tool(name="go_back",
             description="Go back in browser history.",
             inputSchema={"type": "object", "properties": {}}),
        Tool(name="get_url",
             description="Get the current URL and page title.",
             inputSchema={"type": "object", "properties": {}}),
        Tool(name="wait_for",
             description="Wait for a CSS selector to appear, or wait N milliseconds.",
             inputSchema={"type": "object",
                          "properties": {
                              "selector": {"type": "string"},
                              "ms": {"type": "number"},
                          }}),
        Tool(name="close_browser",
             description="Close the sandboxed browser.",
             inputSchema={"type": "object", "properties": {}}),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    try:
        return await _run(name, arguments or {})
    except Exception as e:
        return err(f"{type(e).__name__}: {e}")


async def _run(name: str, a: dict) -> CallToolResult:
    if name == "navigate":
        url = a["url"]
        if any(p.match(url) for p in BLOCKED):
            return err("Blocked by sandbox policy.")
        pg = await get_page()
        await pg.goto(url, wait_until="domcontentloaded", timeout=30_000)
        return ok(f"Navigated to: {url}\nTitle: {await pg.title()}", await snap())

    elif name == "search":
        q = urllib.parse.quote_plus(a["query"])
        pg = await get_page()
        await pg.goto(f"https://www.google.com/search?q={q}",
                      wait_until="domcontentloaded", timeout=30_000)
        return ok(f"Searched: {a['query']}", await snap())

    elif name == "click":
        pg = await get_page()
        sel = a.get("selector")
        txt = a.get("text")
        if sel:
            await pg.click(sel, timeout=10_000)
        elif txt:
            await pg.get_by_text(txt, exact=False).first.click(timeout=10_000)
        else:
            return err("Provide 'selector' or 'text'.")
        await pg.wait_for_timeout(800)
        return ok(f"Clicked: {sel or txt}", await snap())

    elif name == "type_text":
        pg = await get_page()
        if a.get("clear_first", True):
            await pg.fill(a["selector"], "", timeout=10_000)
        await pg.type(a["selector"], a["text"], delay=40)
        return ok(f"Typed into {a['selector']}", await snap())

    elif name == "scroll":
        pg = await get_page()
        amt = a.get("amount", 600)
        delta = amt if a.get("direction", "down") == "down" else -amt
        await pg.evaluate(f"window.scrollBy(0, {delta})")
        await pg.wait_for_timeout(400)
        return ok(f"Scrolled {a.get('direction', 'down')} {amt}px", await snap())

    elif name == "get_text":
        pg = await get_page()
        sel = a.get("selector")
        max_len = int(a.get("max_length", 8000))
        text = (await pg.text_content(sel) if sel
                else await pg.evaluate("() => document.body.innerText")) or ""
        if len(text) > max_len:
            text = text[:max_len] + "\n...[truncated]"
        return ok(text)

    elif name == "screenshot":
        pg = await get_page()
        return ok(f"Screenshot of: {pg.url}", await snap())

    elif name == "go_back":
        pg = await get_page()
        await pg.go_back(wait_until="domcontentloaded", timeout=15_000)
        return ok(f"Back to: {pg.url}", await snap())

    elif name == "get_url":
        pg = await get_page()
        return ok(f"URL: {pg.url}\nTitle: {await pg.title()}")

    elif name == "wait_for":
        pg = await get_page()
        if sel := a.get("selector"):
            await pg.wait_for_selector(sel, timeout=15_000)
            return ok(f"'{sel}' is visible.")
        elif ms := a.get("ms"):
            await pg.wait_for_timeout(int(ms))
            return ok(f"Waited {ms}ms.")
        return err("Provide 'selector' or 'ms'.")

    elif name == "close_browser":
        await close_all()
        return ok("Browser closed.")

    return err(f"Unknown tool: {name}")


# ── Entry point ───────────────────────────────────────────────────────────────
async def main():
    async with stdio_server() as (r, w):
        try:
            await app.run(r, w, app.create_initialization_options())
        finally:
            await close_all()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())

"""Capture three rendered SupportFusion screens for the GitHub README."""

from __future__ import annotations

import asyncio
import base64
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

import websockets


ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "docs" / "images"
SCREENSHOTS = {
    "dashboard": IMAGE_DIR / "dashboard-overview.png",
    "copilot": IMAGE_DIR / "incident-copilot.png",
    "knowledge": IMAGE_DIR / "knowledge-base.png",
}
CHROME_PATH = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
DEVTOOLS_URL = "http://127.0.0.1:9222"
APP_URL = "http://127.0.0.1:5173/"


def devtools_request(path: str) -> dict[str, Any]:
    with urllib.request.urlopen(f"{DEVTOOLS_URL}{path}", timeout=2) as response:
        return json.load(response)


async def capture() -> None:
    if not CHROME_PATH.exists():
        raise FileNotFoundError(f"Chrome was not found at {CHROME_PATH}")

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="supportfusion-chrome-") as profile:
        chrome = subprocess.Popen(
            [
                str(CHROME_PATH),
                "--headless=new",
                "--disable-gpu",
                "--disable-extensions",
                "--no-first-run",
                "--no-default-browser-check",
                "--remote-debugging-address=127.0.0.1",
                "--remote-debugging-port=9222",
                "--remote-allow-origins=*",
                f"--user-data-dir={profile}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        try:
            deadline = time.monotonic() + 15
            targets: list[dict[str, Any]] = []
            while time.monotonic() < deadline:
                if chrome.poll() is not None:
                    raise RuntimeError(
                        "Chrome exited before exposing its DevTools endpoint"
                    )
                try:
                    targets = devtools_request("/json/list")
                    break
                except (OSError, TimeoutError):
                    await asyncio.sleep(0.25)

            page = next(
                (target for target in targets if target.get("type") == "page"), None
            )
            if page is None:
                raise RuntimeError("Chrome did not open a page target")

            async with websockets.connect(
                page["webSocketDebuggerUrl"], max_size=None
            ) as socket:
                command_id = 0

                async def command(
                    method: str, params: dict[str, Any] | None = None
                ) -> dict[str, Any]:
                    nonlocal command_id
                    command_id += 1
                    await socket.send(
                        json.dumps(
                            {"id": command_id, "method": method, "params": params or {}}
                        )
                    )
                    while True:
                        message = json.loads(await socket.recv())
                        if message.get("id") == command_id:
                            if "error" in message:
                                raise RuntimeError(
                                    message["error"].get("message", method)
                                )
                            return message.get("result", {})

                await command(
                    "Emulation.setDeviceMetricsOverride",
                    {
                        "width": 1600,
                        "height": 1100,
                        "deviceScaleFactor": 1,
                        "mobile": False,
                    },
                )
                await command("Page.enable")
                await command("Runtime.enable")
                await command("Page.navigate", {"url": APP_URL})

                async def evaluate(expression: str) -> Any:
                    state = await command(
                        "Runtime.evaluate",
                        {
                            "expression": expression,
                            "returnByValue": True,
                        },
                    )
                    return state.get("result", {}).get("value")

                async def wait_for_screen(description: str, expression: str) -> Any:
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        value = await evaluate(expression)
                        if value:
                            return value
                        await asyncio.sleep(0.4)
                    visible_text = await evaluate("document.body.innerText") or ""
                    raise RuntimeError(
                        f"{description} did not render before capture. "
                        f"Visible page text: {visible_text[:400]}"
                    )

                async def save_screenshot(path: Path) -> None:
                    screenshot = await command(
                        "Page.captureScreenshot",
                        {
                            "format": "png",
                            "fromSurface": True,
                            "captureBeyondViewport": True,
                        },
                    )
                    path.write_bytes(base64.b64decode(screenshot["data"]))
                    print(f"Screenshot: {path}")

                dashboard = await wait_for_screen(
                    "Dashboard",
                    "(()=>{const metric=document.querySelector('.metric-card strong'); if(!document.querySelector('.hero')||!metric)return null; return {incidents:metric.textContent.trim()}})()",
                )
                await save_screenshot(SCREENSHOTS["dashboard"])
                print(f"Dashboard data verified: incidents={dashboard['incidents']}")

                await evaluate(
                    "(()=>{const button=[...document.querySelectorAll('.sidebar nav button')].find(item=>item.innerText.includes('Incident Copilot')); if(!button)return false; button.click(); return true})()"
                )
                await wait_for_screen(
                    "Incident Copilot",
                    "!!document.querySelector('.copilot-layout') && !!document.querySelector('.result-panel .empty-state')",
                )
                await save_screenshot(SCREENSHOTS["copilot"])

                await evaluate(
                    "(()=>{const button=[...document.querySelectorAll('.sidebar nav button')].find(item=>item.innerText.includes('Knowledge Base')); if(!button)return false; button.click(); return true})()"
                )
                await wait_for_screen(
                    "Knowledge Base",
                    "!!document.querySelector('.incident-row .incident-main')",
                )
                await save_screenshot(SCREENSHOTS["knowledge"])
        finally:
            chrome.terminate()
            try:
                chrome.wait(timeout=4)
            except subprocess.TimeoutExpired:
                chrome.kill()


if __name__ == "__main__":
    asyncio.run(capture())

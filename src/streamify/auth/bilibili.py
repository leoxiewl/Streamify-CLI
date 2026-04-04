"""Bilibili QR code login flow."""

from __future__ import annotations

import http.cookiejar
import json
import time
import urllib.request

import qrcode
from rich.console import Console

from streamify.auth.session import save_bilibili_cookies

QR_GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
QR_POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"

POLL_INTERVAL = 2  # seconds
QR_TIMEOUT = 180  # seconds

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://passport.bilibili.com/",
}


def _api_get(url: str, jar: http.cookiejar.CookieJar | None = None) -> dict:
    """Make a GET request to Bilibili API and return parsed JSON."""
    req = urllib.request.Request(url, headers=_HEADERS)
    opener = urllib.request.build_opener()
    if jar is not None:
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    with opener.open(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _generate_qrcode() -> tuple[str, str]:
    """Generate a QR code for login. Returns (qrcode_key, url)."""
    data = _api_get(QR_GENERATE_URL)
    qr_data = data["data"]
    return qr_data["qrcode_key"], qr_data["url"]


def _display_qr(url: str, console: Console) -> None:
    """Display QR code in terminal."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)

    console.print()
    qr.print_ascii(invert=True)
    console.print()
    console.print("[bold]Scan the QR code with Bilibili app to log in[/bold]")
    console.print("[dim]QR code expires in 180 seconds[/dim]")
    console.print()


def _poll_login(qrcode_key: str, console: Console) -> dict | None:
    """Poll login status. Returns cookies dict on success, None on failure."""
    jar = http.cookiejar.CookieJar()
    poll_url = f"{QR_POLL_URL}?qrcode_key={qrcode_key}"
    start = time.time()

    with console.status("[bold blue]Waiting for scan...") as status:
        while time.time() - start < QR_TIMEOUT:
            data = _api_get(poll_url, jar=jar)
            code = data["data"]["code"]

            if code == 0:
                # Login successful — extract cookies from jar
                cookies = {}
                for cookie in jar:
                    if cookie.domain and "bilibili" in cookie.domain:
                        cookies[cookie.name] = cookie.value

                refresh_token = data["data"].get("refresh_token")
                return {"cookies": cookies, "refresh_token": refresh_token}

            elif code == 86090:
                status.update("[bold green]Scanned! Confirm on your phone...")

            elif code == 86038:
                console.print("[yellow]QR code expired.[/yellow]")
                return None

            elif code == 86101:
                pass  # Still waiting for scan

            time.sleep(POLL_INTERVAL)

    console.print("[yellow]Timeout waiting for scan.[/yellow]")
    return None


def bilibili_qr_login(console: Console) -> str | None:
    """Run the full QR login flow. Returns cookie file path on success."""
    max_attempts = 2

    for attempt in range(max_attempts):
        if attempt > 0:
            console.print("[dim]Generating new QR code...[/dim]")

        try:
            qrcode_key, url = _generate_qrcode()
        except Exception as e:
            console.print(f"[red]Failed to generate QR code: {e}[/red]")
            return None

        _display_qr(url, console)
        result = _poll_login(qrcode_key, console)

        if result:
            cookies = result["cookies"]
            if not cookies:
                console.print("[red]Login succeeded but no cookies received.[/red]")
                return None

            path = save_bilibili_cookies(cookies, result.get("refresh_token"))
            return str(path)

        # QR expired or timeout — retry once
        if attempt < max_attempts - 1:
            console.print("[dim]Retrying...[/dim]")

    return None

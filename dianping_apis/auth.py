"""Persistent, user-operated login for the Dianping consumer website."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .errors import AccessRequired

if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserContext, Page, Playwright


NOTE_URL = "https://www.dianping.com/note/create"


class DianpingAuth:
    """Own a Chrome context. The user completes login in its window.

    A `user_data_dir` holds browser cookies and must remain outside the Git tree.
    Pass None for an in-memory context that discards cookies on close.
    """

    def __init__(self, user_data_dir: str | Path | None = None, *, headless: bool = False):
        self.user_data_dir = Path(user_data_dir).expanduser().resolve() if user_data_dir is not None else None
        self.headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def open(self) -> "DianpingAuth":
        if self.context is not None:
            return self
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        try:
            if self.user_data_dir is None:
                self._browser = self._playwright.chromium.launch(channel="chrome", headless=self.headless)
                self.context = self._browser.new_context()
            else:
                self.user_data_dir.mkdir(parents=True, exist_ok=True)
                self.context = self._playwright.chromium.launch_persistent_context(
                    str(self.user_data_dir), channel="chrome", headless=self.headless
                )
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        except Exception:
            if self.context is not None:
                self.context.close()
                self.context = None
            if self._browser is not None:
                self._browser.close()
                self._browser = None
            self._playwright.stop()
            self._playwright = None
            raise
        return self

    def login(self, *, timeout_ms: int = 180_000) -> "DianpingAuth":
        """Show Dianping's own login page and wait for the requested page.

        This method does not handle passwords, SMS codes, or QR contents.  The
        account owner completes those controls in the visible Chrome window.
        """
        page = self.require_page()
        page.goto(NOTE_URL, wait_until="domcontentloaded")
        if "account.dianping.com" in page.url or "verify.meituan.com" in page.url:
            page.wait_for_url(
                lambda url: "account.dianping.com" not in str(url) and "verify.meituan.com" not in str(url),
                timeout=timeout_ms,
            )
        self.require_login()
        return self

    def from_cookie(self, cookie_header: str) -> "DianpingAuth":
        """Import a cookie header from the account owner's own session."""
        if not cookie_header.strip():
            raise ValueError("cookie_header is empty")
        context = self.open().context
        assert context is not None
        cookies = []
        for part in cookie_header.split(";"):
            name, sep, value = part.strip().partition("=")
            if sep and name:
                cookies.append({"name": name, "value": value, "domain": ".dianping.com", "path": "/"})
        if not cookies:
            raise ValueError("cookie_header has no valid name=value pair")
        context.add_cookies(cookies)
        self.require_login()
        return self

    def require_page(self) -> "Page":
        if self.page is None:
            self.open()
        assert self.page is not None
        return self.page

    def require_login(self) -> None:
        page = self.require_page()
        page.goto(NOTE_URL, wait_until="domcontentloaded")
        if "account.dianping.com" in page.url or "verify.meituan.com" in page.url:
            raise AccessRequired("Dianping login or interactive verification is required")

    def close(self) -> None:
        if self.context is not None:
            self.context.close()
            self.context = None
            self.page = None
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    def __enter__(self) -> "DianpingAuth":
        return self.open()

    def __exit__(self, *_exc: object) -> None:
        self.close()

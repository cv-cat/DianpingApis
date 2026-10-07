"""Read-only consumer site operations using a user-controlled browser page."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import quote, urlparse

from bs4 import BeautifulSoup

from .auth import DianpingAuth
from .errors import AccessRequired, ElementMissing
from .models import Item, SearchResult

if TYPE_CHECKING:
    from playwright.sync_api import Page


SHOP_PATH = re.compile(r"^/shop/([^/?#]+)")
ITEM_PATH = re.compile(r"^/(shop|note|review)/([^/?#]+)")
SEARCH_URL = "https://www.dianping.com/search/keyword/{city_id}/0_{keyword}"


def _validate_item_url(url: str) -> tuple[str, str]:
    parts = urlparse(url)
    if parts.scheme != "https" or parts.hostname not in {"www.dianping.com", "m.dianping.com"}:
        raise ValueError("item URL must be an HTTPS dianping.com shop, note, or review URL")
    match = ITEM_PATH.match(parts.path)
    if match is None:
        raise ValueError("item URL path must start with /shop/, /note/, or /review/")
    return match.group(1), match.group(2)


def _text(node: object) -> str:
    return node.get_text(" ", strip=True) if node is not None else ""


def _meta(soup: BeautifulSoup, name: str) -> str:
    node = soup.select_one(f'meta[property="{name}"]')
    if node is None:
        node = soup.select_one(f'meta[name="{name}"]')
    return str(node.get("content", "")).strip() if node is not None else ""


class DianpingAPI:
    """Browser wrapper for shop search and item pages.

    The public search route is protected in some environments.  This class
    reports the verification wall instead of returning it as an empty result.
    """

    def __init__(self, auth_or_page: DianpingAuth | "Page"):
        self.page = auth_or_page.require_page() if isinstance(auth_or_page, DianpingAuth) else auth_or_page

    def _check_access(self, status: int | None = None) -> None:
        url = self.page.url
        if status in {401, 403, 429} or "verify.meituan.com" in url or "account.dianping.com" in url:
            raise AccessRequired(f"Dianping asked for login or verification at {url}")
        html = self.page.content()
        if "验证中心" in html or "人机验证" in html:
            raise AccessRequired("Dianping search requested interactive verification")

    def search(self, keyword: str, *, city_id: int = 1, kind: str = "shop") -> list[SearchResult]:
        """Search visible website results; ``kind`` may be shop, note, or all."""
        if not keyword.strip():
            raise ValueError("keyword is empty")
        if city_id <= 0:
            raise ValueError("city_id must be positive")
        if kind not in {"shop", "note", "all"}:
            raise ValueError("kind must be shop, note, or all")
        url = SEARCH_URL.format(city_id=city_id, keyword=quote(keyword.strip(), safe=""))
        response = self.page.goto(url, wait_until="domcontentloaded")
        self._check_access(response.status if response is not None else None)
        soup = BeautifulSoup(self.page.content(), "html.parser")
        found: dict[str, SearchResult] = {}
        allowed = {"shop", "note"} if kind == "all" else {kind}
        for anchor in soup.select('a[href*="/shop/"], a[href*="/note/"]'):
            href = str(anchor.get("href", ""))
            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                href = "https://www.dianping.com" + href
            try:
                item_kind, item_id = _validate_item_url(href)
            except ValueError:
                continue
            if item_kind not in allowed:
                continue
            title = _text(anchor) or str(anchor.get("title", "")).strip()
            if title:
                found[href] = SearchResult(item_id, title, href)
        if not found and ("打开大众点评App" in str(soup) or "去APP查看" in str(soup)):
            raise ElementMissing("This search page only offered the Dianping App")
        return list(found.values())

    def get_item(self, url: str) -> Item:
        """Read a shop, review or note URL supplied by the caller."""
        kind, item_id = _validate_item_url(url)
        response = self.page.goto(url, wait_until="domcontentloaded")
        self._check_access(response.status if response is not None else None)
        soup = BeautifulSoup(self.page.content(), "html.parser")
        title = (
            _text(soup.select_one(".shopName")) if kind == "shop" else ""
        ) or _meta(soup, "og:title") or _text(soup.select_one("h1"))
        if not title and kind == "shop":
            title = _meta(soup, "keywords").split(",", 1)[0].strip()
        title = title or _text(soup.title)
        description = _meta(soup, "og:description") or _meta(soup, "description")
        if not title or title in {"大众点评", "大众点评APP"} or "客户端官方下载中心" in title:
            raise ElementMissing("This page did not expose item details; try an authenticated browser session")
        return Item(item_id, kind, title, self.page.url, description)

    def get_shop(self, shop_id: str) -> Item:
        if not re.fullmatch(r"[A-Za-z0-9]+", shop_id):
            raise ValueError("invalid shop_id")
        return self.get_item(f"https://m.dianping.com/shop/{shop_id}")

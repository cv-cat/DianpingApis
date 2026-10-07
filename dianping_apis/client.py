"""Read-only Dianping consumer operations over a requests session."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote, urlparse

from bs4 import BeautifulSoup

from .auth import DianpingAuth
from .errors import AccessRequired, ElementMissing
from .models import Item, SearchResult


SHOP_PATH = re.compile(r"^/shop/([^/?#]+)")
ITEM_PATH = re.compile(r"^/(shop|note|review)/([^/?#]+)$")
DISCOVERY_PATH = re.compile(r"^/discovery/(\d+)$")
SEARCH_URL = "https://www.dianping.com/search/keyword/{city_id}/0_{keyword}"
DISCOVERY_URL = "https://www.dianping.com/discovery/"
DISCOVERY_CATEGORY_URL = "https://www.dianping.com/discovery/a/{category_id}"


def _validate_item_url(url: str) -> tuple[str, str]:
    parts = urlparse(url)
    if parts.scheme != "https" or parts.hostname not in {"www.dianping.com", "m.dianping.com"}:
        raise ValueError("item URL must be an HTTPS dianping.com item URL")
    discovery = DISCOVERY_PATH.fullmatch(parts.path)
    if discovery:
        return "note", discovery.group(1)
    match = ITEM_PATH.match(parts.path)
    if match is None:
        raise ValueError("item URL path must identify one shop, note, review, or discovery item")
    if match.group(1) == "note" and match.group(2) == "create":
        raise ValueError("/note/create is not a note item")
    return match.group(1), match.group(2)


def _text(node: object) -> str:
    return node.get_text(" ", strip=True) if node is not None else ""


def _meta(soup: BeautifulSoup, name: str) -> str:
    node = soup.select_one(f'meta[property="{name}"]')
    if node is None:
        node = soup.select_one(f'meta[name="{name}"]')
    return str(node.get("content", "")).strip() if node is not None else ""


def _discovery_results(html: str, keyword: str) -> list[SearchResult]:
    """Filter the current official discovery feed; this is not global search."""
    soup = BeautifulSoup(html, "html.parser")
    script = next((node.get_text() for node in soup.select("script") if "window.__dx_dump__=" in node.get_text()), "")
    if not script:
        raise ElementMissing("Dianping discovery feed data was not present")
    try:
        data, _ = json.JSONDecoder().raw_decode(script.split("window.__dx_dump__=", 1)[1].lstrip())
        dump = data["dump"]
        feed = next(node["feedList"] for node in dump.values() if isinstance(node, dict) and "feedList" in node)
    except (ValueError, KeyError, StopIteration, TypeError) as exc:
        raise ElementMissing("Dianping discovery feed structure changed") from exc
    found: dict[str, SearchResult] = {}
    for node_id in feed:
        node = dump.get(str(node_id), {})
        item_id = str(node.get("contentId", ""))
        title = str(node.get("titleInfo", {}).get("title", "")).strip()
        if item_id.isdecimal() and title and keyword.casefold() in title.casefold():
            url = f"https://m.dianping.com/discovery/{item_id}"
            found[url] = SearchResult(item_id, title, url)
    return list(found.values())


def _discovery_item(html: str, url: str, item_id: str) -> Item:
    soup = BeautifulSoup(html, "html.parser")
    title = _text(soup.select_one("#review h1.review-title"))
    content = _text(soup.select_one("#review .content-wrapper"))
    if not title or not content:
        raise ElementMissing("Dianping discovery page did not expose note title and content")
    return Item(item_id, "note", title, url, _meta(soup, "description"), content)


class DianpingAPI:
    """Pure HTTP client for shop search, discovery feeds and item pages."""

    def __init__(self, auth_or_session: DianpingAuth | Any):
        self.auth = auth_or_session if isinstance(auth_or_session, DianpingAuth) else DianpingAuth(session=auth_or_session)

    @staticmethod
    def _status(response: Any) -> int:
        return int(getattr(response, "status_code", getattr(response, "status", 0)) or 0)

    @staticmethod
    def _url(response: Any) -> str:
        return str(getattr(response, "url", "") or "")

    @staticmethod
    def _text_response(response: Any) -> str:
        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text
        raw = getattr(response, "content", b"")
        return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)

    def _check_access(self, response: Any) -> None:
        status = self._status(response)
        url = self._url(response).lower()
        headers = getattr(response, "headers", {}) or {}
        location = str(headers.get("location", "")).lower()
        text = self._text_response(response)
        history = getattr(response, "history", ()) or ()
        if (
            status in {401, 403, 429}
            or "verify.meituan.com" in url
            or "account.dianping.com" in url
            or "verify.meituan.com" in location
            or "account.dianping.com" in location
            or any("account.dianping.com" in self._url(item).lower() for item in history)
            or any("verify.meituan.com" in self._url(item).lower() for item in history)
            or any(marker in text for marker in ("验证中心", "人机验证", "滑块验证"))
        ):
            raise AccessRequired(f"Dianping asked for login or verification at {self._url(response)}")

    def _get(self, url: str) -> Any:
        response = self.auth.request("GET", url, allow_redirects=True)
        self._check_access(response)
        return response

    def search(self, keyword: str, *, city_id: int = 1, kind: str = "shop") -> list[SearchResult]:
        """Search shops, or filter notes in the current discovery feed."""
        if not keyword.strip():
            raise ValueError("keyword is empty")
        if city_id <= 0:
            raise ValueError("city_id must be positive")
        if kind not in {"shop", "note", "all"}:
            raise ValueError("kind must be shop, note, or all")
        if kind == "note":
            return self.search_notes(keyword)
        response = self._get(SEARCH_URL.format(city_id=city_id, keyword=quote(keyword.strip(), safe="")))
        soup = BeautifulSoup(self._text_response(response), "html.parser")
        found: dict[str, tuple[int, SearchResult]] = {}
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
            if anchor.get("data-click-name") in {"shop_iwant_review_click", "shop_avgprice_click"}:
                continue
            title_node = anchor.select_one("h4")
            title = _text(title_node) or _text(anchor) or str(anchor.get("title", "")).strip()
            if not title:
                picture = anchor.select_one("img[alt]")
                title = str(picture.get("alt", "")).strip() if picture else ""
            if title.startswith("人均") or re.fullmatch(r"[\d,]+\s*条评价", title):
                continue
            if title:
                canonical = f"https://www.dianping.com/{item_kind}/{item_id}"
                priority = 3 if anchor.get("data-click-name") == "shop_title_click" or title_node else 1
                if canonical not in found or priority > found[canonical][0]:
                    found[canonical] = (priority, SearchResult(item_id, title, canonical))
        if not found and ("打开大众点评App" in str(soup) or "去APP查看" in str(soup)):
            raise ElementMissing("This search page only offered the Dianping App")
        return [item for _, item in found.values()]

    def search_notes(self, keyword: str, *, category_id: int | None = None, page: int = 1) -> list[SearchResult]:
        """Filter titles on one official discovery page."""
        if not keyword.strip():
            raise ValueError("keyword is empty")
        if category_id is not None and category_id <= 0:
            raise ValueError("category_id must be positive")
        if page <= 0:
            raise ValueError("page must be positive")
        url = DISCOVERY_CATEGORY_URL.format(category_id=category_id) if category_id is not None else DISCOVERY_URL
        if page > 1:
            url = url.rstrip("/") + f"/p{page}"
        return _discovery_results(self._get(url).text, keyword.strip())

    def get_item(self, url: str) -> Item:
        """Read a shop, review or note URL supplied by the caller."""
        kind, item_id = _validate_item_url(url)
        response = self._get(url)
        actual_url = self._url(response) or url
        try:
            actual_kind, actual_id = _validate_item_url(actual_url)
        except ValueError as exc:
            raise ElementMissing("The item URL redirected to a page without item details") from exc
        if (actual_kind, actual_id) != (kind, item_id):
            raise ElementMissing("The item URL redirected to a different item")
        html = self._text_response(response)
        if DISCOVERY_PATH.fullmatch(urlparse(actual_url).path):
            return _discovery_item(html, actual_url, item_id)
        soup = BeautifulSoup(html, "html.parser")
        page_title = _text(soup.title)
        if "发现好去处" in page_title or "客户端官方下载中心" in page_title:
            raise ElementMissing("This page did not expose item details; try an authenticated HTTP session")
        title = (_text(soup.select_one(".shopName")) if kind == "shop" else "") or _meta(soup, "og:title") or _text(soup.select_one("h1"))
        if not title and kind == "shop":
            title = _meta(soup, "keywords").split(",", 1)[0].strip()
        title = title or page_title
        description = _meta(soup, "og:description") or _meta(soup, "description")
        if not title or title in {"大众点评", "大众点评APP"} or "客户端官方下载中心" in title or "发现好去处" in title:
            raise ElementMissing("This page did not expose item details; try an authenticated HTTP session")
        return Item(item_id, kind, title, actual_url, description)

    def get_shop(self, shop_id: str) -> Item:
        if not re.fullmatch(r"[A-Za-z0-9]+", shop_id):
            raise ValueError("invalid shop_id")
        return self.get_item(f"https://m.dianping.com/shop/{shop_id}")

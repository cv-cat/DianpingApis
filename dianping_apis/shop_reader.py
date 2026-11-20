"""Dish menus and customer reviews read from the Dianping mobile item pages.

2026-11-20 verified live: shop pages embed ``dishName`` objects and
``/shop/{id}/review_all`` renders server-side review items for a logged-in
session. The desktop domain keeps its verification wall; these reads only
target ``m.dianping.com``.
"""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any

from bs4 import BeautifulSoup

from .client import DianpingAPI, _text
from .errors import ElementMissing
from .models import Dish, Review

_SHOP_ID_RE = re.compile(r"^[A-Za-z0-9]+$")
_DISH_OBJECT_RE = re.compile(r"\{[^{}]*\"dishName\"\s*:\s*\"([^\"]+)\"[^{}]*\}")
_REVIEW_SPLIT_RE = re.compile(r"<div class=\"review-item")
_REVIEW_TIME_RE = re.compile(r"seed-add-time\"[^>]*>([^<]+)<")
_REVIEW_TEXT_RE = re.compile(r"seed-feed-content-txt[^>]*>([\s\S]*?)</div>")
_TAG_RE = re.compile(r"<[^>]+>")


def _check_shop_id(shop_id: str) -> None:
    if not _SHOP_ID_RE.fullmatch(shop_id):
        raise ValueError("invalid shop_id")


class DianpingShopReader:
    """Dishes and reviews for a shop, over the same authenticated session."""

    def __init__(self, api: DianpingAPI):
        self.api = api

    def dishes(self, shop_id: str) -> list[Dish]:
        """Signature/recommended dishes embedded in the mobile shop page.

        Each dish object carries ``dishName`` and usually ``price``; entries
        flagged ``recommend``/``zhaopai`` in the surrounding JSON are the
        signature dishes.
        """
        _check_shop_id(shop_id)
        response = self.api._get(f"https://m.dianping.com/shop/{shop_id}")
        html = self.api._text_response(response)
        dishes: list[Dish] = []
        for match in _DISH_OBJECT_RE.finditer(html):
            raw = match.group(0)
            name = match.group(1)
            price: float | None = None
            try:
                payload = json.loads(raw)
                value = payload.get("price")
                if isinstance(value, (int, float)):
                    price = float(value)
            except json.JSONDecodeError:
                pass
            signature = "recommend" in raw or "zhaopai" in raw
            dishes.append(Dish(shop_id, name, price, signature))
        if not dishes:
            raise ElementMissing("Shop page did not expose dish objects; an authenticated session may be required")
        return dishes

    def reviews(self, shop_id: str, *, limit: int | None = None) -> list[Review]:
        """Customer reviews from ``/shop/{id}/review_all`` (server-rendered)."""
        _check_shop_id(shop_id)
        response = self.api._get(f"https://m.dianping.com/shop/{shop_id}/review_all")
        html = self.api._text_response(response)
        if "客户端官方下载中心" in html:
            raise ElementMissing("Review page hit the verification wall; an authenticated session is required")
        reviews: list[Review] = []
        for block in _REVIEW_SPLIT_RE.split(html)[1:]:
            time_match = _REVIEW_TIME_RE.search(block)
            text_match = _REVIEW_TEXT_RE.search(block)
            if not text_match:
                continue
            text = unescape(_TAG_RE.sub("", text_match.group(1)))
            text = " ".join(text.split())
            if not text:
                continue
            reviews.append(Review(shop_id, time_match.group(1) if time_match else None, text))
            if limit is not None and len(reviews) >= limit:
                break
        return reviews

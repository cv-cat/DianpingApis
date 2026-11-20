"""Contract tests for the shop dish/review readers."""

from __future__ import annotations

import unittest

from dianping_apis import Dish, DianpingShopReader, Review
from dianping_apis.errors import ElementMissing


class _FakeResponse:
    def __init__(self, text: str, url: str = ""):
        self.content = text.encode("utf-8")
        self.url = url
        self.status_code = 200
        self.headers: dict[str, str] = {}
        self.history: list = []


class _FakeAuth:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages

    def request(self, method: str, url: str, **_kwargs):
        return _FakeResponse(self.pages[url], url)


class _API:
    def __init__(self, pages: dict[str, str]):
        self.auth = _FakeAuth(pages)

    def _get(self, url: str):
        return self.auth.request("GET", url)

    @staticmethod
    def _text_response(response):
        return response.content.decode("utf-8")


SHOP_PAGE = (
    "<html><body>"
    '<script>var dishes=[{"dishName":"生椰拿铁","price":18,"recommend":true},'
    '{"dishName":"小黄油拿铁","price":20}];</script>'
    "</body></html>"
)

REVIEW_PAGE = (
    "<html><body>"
    '<div class="review-item"><span class="seed-add-time">11月12日 6:25</span>'
    '<div class="seed-feed-content-txt">好喝不腻。</div></div>'
    '<div class="review-item"><span class="seed-add-time">11月9日 23:07</span>'
    '<div class="seed-feed-content-txt"><em>环境</em>安静。</div></div>'
    '<div class="review-item"></div>'
    "</body></html>"
)

WALL_PAGE = "<html><title>大众点评 客户端官方下载中心</title></html>"


def _reader(pages: dict[str, str]) -> DianpingShopReader:
    return DianpingShopReader(_API(pages))  # type: ignore[arg-type]


class DishReaderTests(unittest.TestCase):
    def test_dishes_parse_name_price_and_signature_flag(self):
        reader = _reader({"https://m.dianping.com/shop/abc123": SHOP_PAGE})
        dishes = reader.dishes("abc123")
        self.assertEqual([d.name for d in dishes], ["生椰拿铁", "小黄油拿铁"])
        self.assertTrue(dishes[0].signature)
        self.assertFalse(dishes[1].signature)
        self.assertEqual(dishes[0].price, 18.0)

    def test_dishes_reject_invalid_shop_id(self):
        reader = _reader({})
        with self.assertRaises(ValueError):
            reader.dishes("../escape")

    def test_dishes_without_objects_raises(self):
        reader = _reader({"https://m.dianping.com/shop/abc123": "<html></html>"})
        with self.assertRaises(ElementMissing):
            reader.dishes("abc123")


class ReviewReaderTests(unittest.TestCase):
    def test_reviews_parse_time_and_plain_text(self):
        reader = _reader({"https://m.dianping.com/shop/abc123/review_all": REVIEW_PAGE})
        reviews = reader.reviews("abc123")
        self.assertEqual(len(reviews), 2)
        self.assertEqual(reviews[0].time, "11月12日 6:25")
        self.assertEqual(reviews[0].text, "好喝不腻。")
        self.assertEqual(reviews[1].text, "环境安静。")

    def test_reviews_respect_limit(self):
        reader = _reader({"https://m.dianping.com/shop/abc123/review_all": REVIEW_PAGE})
        self.assertEqual(len(reader.reviews("abc123", limit=1)), 1)

    def test_reviews_hit_verification_wall(self):
        reader = _reader({"https://m.dianping.com/shop/abc123/review_all": WALL_PAGE})
        with self.assertRaises(ElementMissing):
            reader.reviews("abc123")

    def test_review_model_fields(self):
        review = Review("abc123", "11月12日 6:25", "text")
        self.assertEqual((review.shop_id, review.time, review.text), ("abc123", "11月12日 6:25", "text"))
        dish = Dish("abc123", "拿铁", 18.0, True)
        self.assertEqual((dish.shop_id, dish.name, dish.price, dish.signature), ("abc123", "拿铁", 18.0, True))


if __name__ == "__main__":
    unittest.main()

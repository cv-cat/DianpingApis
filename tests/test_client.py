from types import SimpleNamespace

import pytest

from dianping_apis import AccessRequired, DianpingAPI, ElementMissing
from dianping_apis.client import _validate_item_url


class FakePage:
    def __init__(self, html, *, status=200):
        self.html = html
        self.status = status
        self.url = "about:blank"

    def goto(self, url, **_kwargs):
        self.url = url
        return SimpleNamespace(status=self.status)

    def content(self):
        return self.html


def test_search_extracts_shops_and_deduplicates_links():
    page = FakePage('''<a href="/shop/123">茶馆</a>
        <a href="/shop/123">茶馆</a>
        <a href="https://www.dianping.com/shop/456">饭店</a>
        <a href="/note/789">探店</a>
        <a href="https://evil.example/shop/1">外站</a>''')
    result = DianpingAPI(page).search("咖啡", city_id=1)
    assert [(item.id, item.title) for item in result] == [("123", "茶馆"), ("456", "饭店")]
    assert "%E5%92%96%E5%95%A1" in page.url


def test_search_prefers_shop_name_link_over_review_and_price_links():
    page = FakePage('''<a href="/shop/123"><img alt="咖啡馆"></a>
        <a href="/shop/123" data-click-name="shop_title_click"><h4>咖啡馆</h4></a>
        <a href="/shop/123#comment" data-click-name="shop_iwant_review_click">69 条评价</a>
        <a href="/shop/123" data-click-name="shop_avgprice_click">人均 ￥15</a>''')
    result = DianpingAPI(page).search("咖啡")
    assert result == [type(result[0])("123", "咖啡馆", "https://www.dianping.com/shop/123")]


def test_get_shop_parses_visible_mobile_details():
    page = FakePage('''<html><head><meta property="og:title" content="测试咖啡馆">
        <meta name="description" content="北京 · 人均 90 元"></head><body><h1>测试咖啡馆</h1></body></html>''')
    item = DianpingAPI(page).get_shop("563754")
    assert (item.kind, item.id, item.title) == ("shop", "563754", "测试咖啡馆")
    assert "90" in item.description


def test_get_shop_prefers_actual_shop_name_over_seo_page_title():
    page = FakePage('''<title>测试咖啡馆_电话_地址_价格_营业时间 - 大众点评</title>
        <meta name="keywords" content="测试咖啡馆,测试咖啡馆人均消费">
        <span class="shopName">测试咖啡馆</span>''')
    assert DianpingAPI(page).get_shop("563754").title == "测试咖啡馆"


def test_verification_wall_is_error_not_empty_search():
    with pytest.raises(AccessRequired):
        DianpingAPI(FakePage("验证中心", status=403)).search("火锅")


def test_app_download_landing_is_not_reported_as_shop_details():
    page = FakePage('<html><title>大众点评客户端官方下载中心</title><button>下载大众点评App</button></html>')
    with pytest.raises(ElementMissing):
        DianpingAPI(page).get_shop("18435486")


def test_item_url_is_confined_to_dianping():
    with pytest.raises(ValueError):
        _validate_item_url("https://evil.example/shop/1")
    with pytest.raises(ValueError):
        _validate_item_url("http://www.dianping.com/shop/1")

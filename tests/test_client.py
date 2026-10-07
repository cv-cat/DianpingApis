import pytest

from dianping_apis import AccessRequired, DianpingAPI, DianpingAuth, ElementMissing, SearchResult
from dianping_apis.client import _validate_item_url


class Response:
    def __init__(self, html, *, status=200, url="", headers=None):
        self.status_code = status
        self.status = status
        self.text = html
        self.content = html.encode()
        self.url = url
        self.headers = headers or {}
        self.history = []


class Session:
    def __init__(self, routes):
        self.routes = routes
        self.cookies = type("Cookies", (), {"set": lambda *_args, **_kwargs: None, "get": lambda *_args, **_kwargs: None})()
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        value = self.routes[url]
        return value() if callable(value) else value

    def close(self):
        pass


def api_for(routes):
    return DianpingAPI(DianpingAuth(session=Session(routes)))


def test_search_extracts_shops_and_deduplicates_links():
    html = '''<a href="/shop/123">茶馆</a><a href="/shop/123">茶馆</a>
        <a href="https://www.dianping.com/shop/456">饭店</a>
        <a href="/note/789">探店</a><a href="https://evil.example/shop/1">外站</a>'''
    url = "https://www.dianping.com/search/keyword/1/0_%E5%92%96%E5%95%A1"
    api = api_for({url: Response(html, url=url)})
    result = api.search("咖啡", city_id=1)
    assert [(item.id, item.title) for item in result] == [("123", "茶馆"), ("456", "饭店")]


def test_search_prefers_shop_name_link_over_review_and_price_links():
    html = '''<a href="/shop/123"><img alt="咖啡馆"></a>
        <a href="/shop/123" data-click-name="shop_title_click"><h4>咖啡馆</h4></a>
        <a href="/shop/123#comment" data-click-name="shop_iwant_review_click">69 条评价</a>
        <a href="/shop/123" data-click-name="shop_avgprice_click">人均 ￥15</a>'''
    url = "https://www.dianping.com/search/keyword/1/0_%E5%92%96%E5%95%A1"
    assert api_for({url: Response(html, url=url)}).search("咖啡") == [
        SearchResult("123", "咖啡馆", "https://www.dianping.com/shop/123")
    ]


def test_get_shop_parses_visible_mobile_details():
    url = "https://m.dianping.com/shop/563754"
    html = '<meta property="og:title" content="测试咖啡馆"><meta name="description" content="北京 · 人均 90 元"><h1>测试咖啡馆</h1>'
    item = api_for({url: Response(html, url=url)}).get_shop("563754")
    assert (item.kind, item.id, item.title) == ("shop", "563754", "测试咖啡馆")
    assert "90" in item.description


def test_get_shop_prefers_actual_shop_name_over_seo_page_title():
    url = "https://m.dianping.com/shop/563754"
    html = '<title>测试咖啡馆_电话_地址_价格_营业时间 - 大众点评</title><meta name="keywords" content="测试咖啡馆,测试咖啡馆人均消费"><span class="shopName">测试咖啡馆</span>'
    assert api_for({url: Response(html, url=url)}).get_shop("563754").title == "测试咖啡馆"


def test_verification_wall_is_error_not_empty_search():
    url = "https://www.dianping.com/search/keyword/1/0_%E7%81%AB%E9%94%85"
    with pytest.raises(AccessRequired):
        api_for({url: Response("验证中心", status=403, url=url)}).search("火锅")


def test_app_download_landing_is_not_reported_as_shop_details():
    url = "https://m.dianping.com/shop/18435486"
    with pytest.raises(ElementMissing):
        api_for({url: Response('<title>大众点评客户端官方下载中心</title><button>下载大众点评App</button>', url=url)}).get_shop("18435486")


def test_item_url_is_confined_to_dianping():
    with pytest.raises(ValueError):
        _validate_item_url("https://evil.example/shop/1")
    with pytest.raises(ValueError):
        _validate_item_url("http://www.dianping.com/shop/1")
    with pytest.raises(ValueError, match="not a note item"):
        _validate_item_url("https://www.dianping.com/note/create")


def test_item_redirect_to_homepage_does_not_return_homepage_as_shop():
    url = "https://m.dianping.com/shop/563754"
    with pytest.raises(ElementMissing, match="redirected"):
        api_for({url: Response("<title>大众点评网 - 发现好去处</title>", url="https://m.dianping.com/")}).get_shop("563754")


def test_discovery_feed_filter_and_note_item_content():
    list_url = "https://www.dianping.com/discovery/"
    feed = '''<script>window.__dx_dump__={"dump":{"3":{"feedList":[7,8]},"7":{"contentId":123,"titleInfo":{"title":"咖啡探店"}},"8":{"contentId":456,"titleInfo":{"title":"火锅探店"}}},"entries":[]};</script>'''
    item_url = "https://m.dianping.com/discovery/123"
    item_html = '<title>咖啡探店 - 大众点评</title><meta name="description" content="笔记摘要"><div id="review"><h1 class="review-title">咖啡探店</h1><div class="content-wrapper"><p>真实的笔记正文</p></div></div>'
    api = api_for({list_url: Response(feed, url=list_url), item_url: Response(item_html, url=item_url)})
    matches = api.search("咖啡", kind="note")
    assert [(x.id, x.url) for x in matches] == [("123", item_url)]
    item = api.get_item(matches[0].url)
    assert (item.kind, item.id, item.title, item.content) == ("note", "123", "咖啡探店", "真实的笔记正文")


def test_discovery_note_requires_actual_content_not_generic_page():
    url = "https://m.dianping.com/discovery/123"
    with pytest.raises(ElementMissing, match="note title and content"):
        api_for({url: Response('<title>大众点评网 - 发现好去处</title>', url=url)}).get_item(url)
    with pytest.raises(ValueError):
        _validate_item_url("https://m.dianping.com/discovery/p2")


def test_discovery_note_search_supports_category_and_page():
    url = "https://www.dianping.com/discovery/a/10/p2"
    feed = '<script>window.__dx_dump__={"dump":{"3":{"feedList":[7]},"7":{"contentId":123,"titleInfo":{"title":"咖啡探店"}}},"entries":[]};</script>'
    assert api_for({url: Response(feed, url=url)}).search_notes("咖啡", category_id=10, page=2)[0].id == "123"
    with pytest.raises(ValueError):
        api_for({url: Response(feed, url=url)}).search_notes("咖啡", category_id=0)
    with pytest.raises(ValueError):
        api_for({url: Response(feed, url=url)}).search_notes("咖啡", page=0)

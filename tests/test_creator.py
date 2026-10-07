import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from dianping_apis import DianpingCreatorAPI, ElementMissing, SubmissionUnconfirmed


class FakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    @property
    def first(self):
        return self

    def _matched(self):
        for candidate in self.selector.split(", "):
            base = candidate.removesuffix(":visible")
            if any(self.page.available.get(base, [])):
                return base
        return None

    def count(self):
        return len(self.page.available.get(self.selector, []))

    def is_visible(self):
        return self._matched() is not None

    def wait_for(self, *, state, timeout):
        if state != "visible" or self._matched() is None:
            raise PlaywrightTimeoutError("locator did not become visible")

    def fill(self, value):
        self.page.filled[self._matched()] = value

    def click(self):
        selector = self._matched()
        self.page.clicked.append(selector)
        if "发布" in selector and self.page.redirect_after_submit:
            self.page.url = self.page.redirect_after_submit
        if "发布" in selector and self.page.success_after_submit:
            self.page.available[':text-matches("发布成功|发表成功|提交成功")'] = [True]


class FakePage:
    def __init__(self, available, *, redirect_after_submit=None, success_after_submit=False):
        self.available = {selector: [True] for selector in available}
        self.url = "about:blank"
        self.clicked = []
        self.filled = {}
        self.redirect_after_submit = redirect_after_submit
        self.success_after_submit = success_after_submit

    def goto(self, url, **_kwargs):
        self.url = url

    def locator(self, selector):
        return FakeLocator(self, selector)

    def get_by_role(self, role, *, name, exact):
        return FakeLocator(self, f"role={role}:name={name}")


def test_note_can_be_prepared_without_submitting():
    page = FakePage({'input[placeholder*="标题"]', '[contenteditable="true"]'})
    result = DianpingCreatorAPI(page).publish_note("标题", "正文")
    assert result.confirmation == "form filled; not submitted"
    assert page.filled == {'input[placeholder*="标题"]': "标题", '[contenteditable="true"]': "正文"}
    assert page.clicked == []


def test_review_opens_shop_editor_and_sets_rating_without_submitting():
    page = FakePage({'a:has-text("写点评")', 'textarea[placeholder*="点评"]', '[aria-label="4星"]'})
    result = DianpingCreatorAPI(page).publish_review(
        "https://www.dianping.com/shop/123", "真实体验", rating=4
    )
    assert result.kind == "review"
    assert page.clicked == ['a:has-text("写点评")', '[aria-label="4星"]']
    assert page.filled['textarea[placeholder*="点评"]'] == "真实体验"


def test_hidden_first_editor_is_skipped_and_visible_duplicate_is_filled():
    page = FakePage({'input[placeholder*="标题"]', '[contenteditable="true"]'})
    page.available['input[placeholder*="标题"]'] = [False, True]
    DianpingCreatorAPI(page).publish_note("标题", "正文", submit=False)
    assert page.filled['input[placeholder*="标题"]'] == "标题"


def test_review_redirect_alone_does_not_confirm_submission():
    page = FakePage(
        {'a:has-text("写点评")', 'textarea[placeholder*="点评"]',
         '[aria-label="4星"]', 'button:has-text("发布")'},
        redirect_after_submit="https://www.dianping.com/review/list",
    )
    with pytest.raises(SubmissionUnconfirmed):
        DianpingCreatorAPI(page).publish_review(
            "https://www.dianping.com/shop/123", "真实体验", rating=4, submit=True
        )


def test_shop_name_requires_actual_visible_option():
    page = FakePage({'input[placeholder*="标题"]', '[contenteditable="true"]',
                     'input[placeholder*="店铺"]'})
    with pytest.raises(ElementMissing):
        DianpingCreatorAPI(page).publish_note("标题", "正文", shop_name="测试店", submit=False)


def test_visible_success_signal_after_click_confirms_write():
    page = FakePage(
        {'input[placeholder*="标题"]', '[contenteditable="true"]', 'button:has-text("发布")'},
        success_after_submit=True,
    )
    result = DianpingCreatorAPI(page).publish_note("标题", "正文", submit=True)
    assert result.confirmation == "visible success message"
    assert 'button:has-text("发布")' in page.clicked


def test_stale_success_signal_does_not_confirm_another_write():
    page = FakePage(
        {'input[placeholder*="标题"]', '[contenteditable="true"]',
         'button:has-text("发布")', ':text-matches("发布成功|发表成功|提交成功")'},
    )
    with pytest.raises(SubmissionUnconfirmed):
        DianpingCreatorAPI(page).publish_note("标题", "正文", submit=True)
    assert page.clicked == []

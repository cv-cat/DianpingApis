from dianping_apis import DianpingAuth


class FakeContext:
    def __init__(self):
        self.cookies = None

    def add_cookies(self, cookies):
        self.cookies = cookies


def test_imported_cookie_values_can_contain_equals(monkeypatch, tmp_path):
    auth = DianpingAuth(tmp_path / "browser")
    auth.context = FakeContext()
    monkeypatch.setattr(auth, "open", lambda: auth)
    monkeypatch.setattr(auth, "require_login", lambda: None)
    auth.from_cookie("session=abc==; other=xyz")
    assert auth.context.cookies == [
        {"name": "session", "value": "abc==", "domain": ".dianping.com", "path": "/"},
        {"name": "other", "value": "xyz", "domain": ".dianping.com", "path": "/"},
    ]


def test_temporary_context_does_not_create_profile(monkeypatch):
    class Browser:
        def __init__(self):
            self.closed = False
            self.context = Context()

        def new_context(self):
            return self.context

        def close(self):
            self.closed = True

    class Context:
        pages = []

        def __init__(self):
            self.closed = False

        def new_page(self):
            return object()

        def close(self):
            self.closed = True

    class Chromium:
        def __init__(self):
            self.browser = Browser()

        def launch(self, *, channel, headless):
            assert (channel, headless) == ("chrome", True)
            return self.browser

        def launch_persistent_context(self, *_args, **_kwargs):
            raise AssertionError("temporary auth must not create a persistent profile")

    class Playwright:
        def __init__(self):
            self.chromium = Chromium()
            self.stopped = False

        def stop(self):
            self.stopped = True

    playwright = Playwright()
    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: type("Starter", (), {"start": lambda _self: playwright})())
    auth = DianpingAuth(None, headless=True).open()
    assert auth.user_data_dir is None
    auth.close()
    assert playwright.chromium.browser.context.closed
    assert playwright.chromium.browser.closed
    assert playwright.stopped

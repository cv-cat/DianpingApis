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

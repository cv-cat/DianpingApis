from types import SimpleNamespace

import pytest

from dianping_apis import AccessRequired, DianpingAuth
from dianping_apis.auth import QR_IMAGE_URL


class CookieJar:
    def __init__(self):
        self.values = {}

    def set(self, name, value, **_kwargs):
        self.values[name] = value

    def get(self, name, default=None):
        return self.values.get(name, default)


class Response:
    def __init__(self, *, status=200, url="https://www.dianping.com/note/create", text="ok", content=None, headers=None, json_data=None):
        self.status_code = status
        self.status = status
        self.url = url
        self.text = text
        self.content = content if content is not None else text.encode()
        self.headers = headers or {}
        self.history = []
        self._json_data = json_data

    def json(self):
        if self._json_data is None:
            raise ValueError("not json")
        return self._json_data


class Session:
    def __init__(self, responses):
        self.cookies = CookieJar()
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        return response

    def close(self):
        pass


def test_cookie_header_preserves_equals_and_uses_http_only_session():
    session = Session([Response()])
    auth = DianpingAuth(session=session)
    auth._load_cookie_header("session=abc==; other=xyz")
    assert session.cookies.values == {"session": "abc==", "other": "xyz"}
    auth.require_login()
    assert session.calls[0][0:2] == ("GET", "https://www.dianping.com/note/create")


def test_cookie_login_rejects_redirect_to_account():
    session = Session([Response(status=302, headers={"location": "https://account.dianping.com/pclogin"})])
    with pytest.raises(AccessRequired):
        DianpingAuth.from_cookie("session=x", session=session)


def test_qr_start_requires_real_h5guard_values_and_keeps_image_in_memory():
    session = Session([Response(content=b"jpeg", headers={"content-type": "image/jpeg"})])
    session.cookies.set("qruuid", "uuid-1")
    auth = DianpingAuth(session=session)
    with pytest.raises(ValueError):
        auth.start_qr_login(h5_fingerprint="", mtgsig="sig")
    challenge = auth.start_qr_login(h5_fingerprint="fp", mtgsig="sig")
    assert challenge.qruuid == "uuid-1"
    assert challenge.image == b"jpeg"
    assert challenge.image_data_url.startswith("data:image/jpeg;base64,")
    assert session.calls[0][1] == QR_IMAGE_URL
    assert session.calls[0][2]["params"]["risk_app"] == 216
    assert session.calls[0][2]["headers"]["mtgsig"] == "sig"


def test_login_does_not_open_browser_or_guess_signature():
    auth = DianpingAuth(session=Session([]))
    with pytest.raises(AccessRequired, match="H5guard"):
        auth.login()

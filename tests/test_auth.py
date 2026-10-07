from types import SimpleNamespace

import pytest

from dianping_apis import AccessRequired, DianpingAuth, H5GuardRequired
from dianping_apis.auth import CACHE_TOKEN_P_URL, CACHE_TOKEN_URL, CHECK_LOGIN_URL, QR_CHECK_URL, QR_IMAGE_URL


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
    with pytest.raises(H5GuardRequired, match="h5_fingerprint"):
        auth.start_qr_login(h5_fingerprint="", mtgsig="sig")
    challenge = auth.start_qr_login(h5_fingerprint="fp", mtgsig="sig")
    assert challenge.qruuid == "uuid-1"
    assert challenge.image == b"jpeg"
    assert challenge.image_data_url.startswith("data:image/jpeg;base64,")
    assert session.calls[0][1] == QR_IMAGE_URL
    assert [name for name, _ in session.calls[0][2]["params"]] == [
        "risk_app",
        "risk_partner",
        "risk_platform",
        "h5_fingerprint",
        "yodaReady",
        "csecplatform",
        "csecversion",
    ]
    assert session.calls[0][2]["params"][0] == ("risk_app", "216")
    assert session.calls[0][2]["headers"]["mtgsig"] == "sig"


def test_guest_bootstrap_matches_cache_token_then_check_login_contract():
    responses = [
        Response(text="cache-a", url=CACHE_TOKEN_URL),
        Response(text="cache-b", url=CACHE_TOKEN_P_URL),
        Response(text='{"login":false}', url=CHECK_LOGIN_URL, json_data={"login": False}),
    ]
    session = Session(responses)
    auth = DianpingAuth(session=session)
    result = auth.bootstrap_guest(h5_fingerprint="fp", mtgsig='{"a1":"x"}')
    assert result["check_login"] == {"login": False}
    assert [call[1] for call in session.calls] == [CACHE_TOKEN_URL, CACHE_TOKEN_P_URL, CHECK_LOGIN_URL]
    method, url, kwargs = session.calls[2]
    assert method == "POST"
    assert [name for name, _ in kwargs["params"]] == ["yodaReady", "csecplatform", "csecversion", "mtgsig"]
    assert kwargs["data"] == b""
    assert kwargs["headers"]["Origin"] == "https://account.dianping.com"


def test_guest_bootstrap_can_stop_before_h5guard_check():
    session = Session([Response(text="cache-a", url=CACHE_TOKEN_URL), Response(text="cache-b", url=CACHE_TOKEN_P_URL)])
    result = DianpingAuth(session=session).bootstrap_guest()
    assert result["check_login"]["skipped"] is True
    assert [call[1] for call in session.calls] == [CACHE_TOKEN_URL, CACHE_TOKEN_P_URL]


def test_guest_bootstrap_rejects_partial_h5guard_evidence_explicitly():
    responses = [
        Response(text="cache-a", url=CACHE_TOKEN_URL),
        Response(text="cache-b", url=CACHE_TOKEN_P_URL),
    ]
    auth = DianpingAuth(session=Session(responses))
    with pytest.raises(H5GuardRequired, match="both current"):
        auth.bootstrap_guest(h5_fingerprint="fp")


def test_qr_poll_reads_nested_browser_status_and_keeps_parameter_order():
    waiting = Response(
        url="https://accountapi.dianping.com/mlogin/dp/api/v1/qrlogin/check",
        json_data={"code": 0, "data": {"status": 200, "description": "用户未扫描二维码"}},
    )
    session = Session([waiting] * 10)
    session.cookies.set("qruuid", "uuid-1")
    auth = DianpingAuth(session=session)
    challenge = type("Challenge", (), {"qruuid": "uuid-1", "check_url": "https://accountapi.dianping.com/mlogin/dp/api/v1/qrlogin/check"})()
    with pytest.raises(TimeoutError):
        auth.poll_qr_login(challenge, h5_fingerprint="fp", mtgsig="sig", interval=0.05, timeout=0.06)
    params = session.calls[0][2]["params"]
    assert [name for name, _ in params] == [
        "qruuid",
        "risk_app",
        "risk_partner",
        "risk_platform",
        "h5_fingerprint",
        "yodaReady",
        "csecplatform",
        "csecversion",
    ]


def test_login_does_not_open_browser_or_guess_signature():
    auth = DianpingAuth(session=Session([]))
    with pytest.raises(H5GuardRequired, match="H5guard"):
        auth.login()


def test_qr_poll_empty_signature_callback_is_explicit_h5guard_error():
    auth = DianpingAuth(session=Session([]))
    challenge = type("Challenge", (), {"qruuid": "uuid-1", "check_url": QR_CHECK_URL})()
    with pytest.raises(H5GuardRequired, match="mtgsig"):
        auth.poll_qr_login(
            challenge,
            h5_fingerprint="fp",
            mtgsig=lambda _qruuid: "",
            timeout=0.1,
        )

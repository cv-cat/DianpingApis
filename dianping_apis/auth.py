"""HTTP-only Dianping authentication and QR challenge helpers.

The consumer login page uses Meituan H5guard to produce ``h5_fingerprint``
and ``mtgsig``.  This module deliberately does not launch a browser or fake
those values.  Callers can supply values produced by an authorised, normal
H5guard flow and then poll the QR endpoint with the same HTTP session.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urljoin

import requests

from .errors import AccessRequired, DianpingError


NOTE_URL = "https://www.dianping.com/note/create"
QR_IMAGE_URL = "https://accountapi.dianping.com/mlogin/dp/api/v1/qrlogin/getQrCodeImg"
QR_CHECK_URL = "https://accountapi.dianping.com/mlogin/dp/api/v1/qrlogin/check"
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
}


@dataclass(frozen=True)
class QRLoginChallenge:
    """A QR image and the opaque id used by the check endpoint."""

    qruuid: str
    image: bytes
    image_content_type: str
    check_url: str = QR_CHECK_URL

    @property
    def image_data_url(self) -> str:
        """Return a data URL suitable for a caller-owned UI."""
        encoded = base64.b64encode(self.image).decode("ascii")
        return f"data:{self.image_content_type};base64,{encoded}"


class DianpingAuth:
    """Own a requests session for Dianping's HTTP endpoints.

    ``user_data_dir`` and ``headless`` are retained as ignored compatibility
    arguments for callers of the former browser wrapper.  No profile is read,
    no browser is launched and no automation module is imported.
    """

    def __init__(
        self,
        user_data_dir: str | Path | None = None,
        *,
        headless: bool | None = None,
        cookie_header: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 20.0,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.user_data_dir = Path(user_data_dir).expanduser().resolve() if user_data_dir else None
        self.headless = headless
        self.timeout = timeout
        self.session = session or requests.Session()
        self.headers = dict(DEFAULT_HEADERS)
        if headers:
            self.headers.update(headers)
        if cookie_header:
            self._load_cookie_header(cookie_header)

    def open(self) -> "DianpingAuth":
        """Compatibility no-op returning this HTTP session."""
        return self

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Send an HTTP request with the observed Dianping browser headers."""
        headers = dict(self.headers)
        headers.update(kwargs.pop("headers", {}) or {})
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("allow_redirects", False)
        return self.session.request(method, url, headers=headers, **kwargs)

    def _load_cookie_header(self, cookie_header: str) -> None:
        if not cookie_header.strip():
            raise ValueError("cookie_header is empty")
        loaded = 0
        for part in cookie_header.split(";"):
            name, sep, value = part.strip().partition("=")
            if sep and name.strip():
                self.session.cookies.set(name.strip(), value, domain=".dianping.com", path="/")
                loaded += 1
        if not loaded:
            raise ValueError("cookie_header has no valid name=value pair")

    @classmethod
    def from_cookie(
        cls,
        cookie_header: str,
        *,
        session: requests.Session | None = None,
        timeout: float = 20.0,
    ) -> "DianpingAuth":
        auth = cls(session=session, timeout=timeout)
        auth._load_cookie_header(cookie_header)
        auth.require_login()
        return auth

    @staticmethod
    def _response_url(response: Any) -> str:
        return str(getattr(response, "url", "") or "")

    @staticmethod
    def _response_text(response: Any) -> str:
        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text
        raw = getattr(response, "content", b"")
        return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)

    @classmethod
    def _is_challenge_response(cls, response: Any) -> bool:
        status = int(getattr(response, "status_code", getattr(response, "status", 0)) or 0)
        url = cls._response_url(response).lower()
        headers = getattr(response, "headers", {}) or {}
        location = str(headers.get("location", "")).lower()
        text = cls._response_text(response)
        return (
            status in {401, 403, 429}
            or "account.dianping.com" in url
            or "verify.meituan.com" in url
            or "account.dianping.com" in location
            or "verify.meituan.com" in location
            or any(marker in text for marker in ("验证中心", "人机验证", "滑块验证"))
        )

    def require_login(self) -> None:
        response = self.request("GET", NOTE_URL, allow_redirects=False)
        if self._is_challenge_response(response):
            location = str((getattr(response, "headers", {}) or {}).get("location", ""))
            raise AccessRequired(
                "Dianping requires login or interactive verification"
                + (f" at {urljoin(NOTE_URL, location)}" if location else "")
            )

    def start_qr_login(
        self,
        *,
        h5_fingerprint: str,
        mtgsig: str,
        risk_app: int = 216,
        risk_partner: int = 26,
        risk_platform: int = 2,
        yoda_ready: str = "h5",
        csec_platform: int = 4,
        csec_version: str = "4.3.0",
        on_image: Callable[[bytes, str], None] | None = None,
    ) -> QRLoginChallenge:
        """Request a QR image using caller-supplied H5guard evidence."""
        if not h5_fingerprint.strip() or not mtgsig.strip():
            raise ValueError("h5_fingerprint and mtgsig are required")
        params = {
            "risk_app": risk_app,
            "risk_partner": risk_partner,
            "risk_platform": risk_platform,
            "h5_fingerprint": h5_fingerprint,
            "yodaReady": yoda_ready,
            "csecplatform": csec_platform,
            "csecversion": csec_version,
        }
        response = self.request("GET", QR_IMAGE_URL, params=params, headers={"mtgsig": mtgsig})
        status = int(getattr(response, "status_code", 0) or 0)
        if status != 200 or self._is_challenge_response(response):
            raise AccessRequired("Dianping QR endpoint rejected the H5guard challenge")
        image = getattr(response, "content", b"")
        content_type = str((getattr(response, "headers", {}) or {}).get("content-type", "image/jpeg"))
        if not isinstance(image, bytes) or not image:
            raise DianpingError("Dianping QR endpoint returned no image")
        qruuid = str(self.session.cookies.get("qruuid", ""))
        if not qruuid:
            raise DianpingError("Dianping QR endpoint did not set qruuid")
        if on_image:
            on_image(image, content_type)
        return QRLoginChallenge(qruuid=qruuid, image=image, image_content_type=content_type)

    def poll_qr_login(
        self,
        challenge: QRLoginChallenge,
        *,
        h5_fingerprint: str,
        mtgsig: str | Callable[[str], str],
        risk_app: int = 216,
        risk_partner: int = 26,
        risk_platform: int = 2,
        interval: float = 2.0,
        timeout: float = 180.0,
    ) -> Mapping[str, Any]:
        """Poll after the user scans in the official Dianping app."""
        if not h5_fingerprint.strip():
            raise ValueError("h5_fingerprint is required")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            signature = mtgsig(challenge.qruuid) if callable(mtgsig) else mtgsig
            params = {
                "qruuid": challenge.qruuid,
                "risk_app": risk_app,
                "risk_partner": risk_partner,
                "risk_platform": risk_platform,
                "h5_fingerprint": h5_fingerprint,
            }
            response = self.request("GET", challenge.check_url, params=params, headers={"mtgsig": signature})
            status = int(getattr(response, "status_code", 0) or 0)
            if status != 200:
                raise AccessRequired("Dianping QR status request was rejected")
            try:
                data = response.json()
            except (AttributeError, ValueError) as exc:
                raise DianpingError("Dianping QR status was not JSON") from exc
            if not isinstance(data, Mapping):
                raise DianpingError("Dianping QR status had an unexpected shape")
            state = str(data.get("status", data.get("code", data.get("errno", "")))).lower()
            if state not in {"", "0", "pending", "wait", "waiting", "1"}:
                return data
            if data.get("login") is True or data.get("isLogin") is True:
                return data
            time.sleep(max(0.05, interval))
        raise TimeoutError("Dianping QR login timed out; scan the current QR code and retry")

    def login(self, *, timeout_ms: int = 180_000, **kwargs: Any) -> "DianpingAuth":
        """Run an HTTP-only QR flow when H5guard evidence is supplied."""
        fingerprint = kwargs.pop("h5_fingerprint", None)
        signature = kwargs.pop("mtgsig", None)
        if kwargs:
            raise TypeError(f"unexpected login arguments: {', '.join(sorted(kwargs))}")
        if not fingerprint or not signature:
            raise AccessRequired(
                "Dianping QR login is protected by H5guard; supply h5_fingerprint and mtgsig "
                "from the normal login challenge, then poll_qr_login after scanning"
            )
        challenge = self.start_qr_login(h5_fingerprint=fingerprint, mtgsig=signature)
        self.poll_qr_login(
            challenge,
            h5_fingerprint=fingerprint,
            mtgsig=signature,
            timeout=max(0.0, timeout_ms / 1000),
        )
        self.require_login()
        return self

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "DianpingAuth":
        return self.open()

    def __exit__(self, *_exc: object) -> None:
        self.close()

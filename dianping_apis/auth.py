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
LOGIN_PAGE_URL = "https://account.dianping.com/pclogin"
ACCOUNT_ORIGIN = "https://account.dianping.com"
ACCOUNT_REFERER = "https://account.dianping.com/"
CACHE_TOKEN_URL = "https://msp.meituan.com/web/cache-token"
CACHE_TOKEN_P_URL = "https://msp.meituan.com/web/cache-token-p"
CHECK_LOGIN_URL = "https://m.dianping.com/account/ajax/checkLogin"
QR_IMAGE_URL = "https://accountapi.dianping.com/mlogin/dp/api/v1/qrlogin/getQrCodeImg"
QR_CHECK_URL = "https://accountapi.dianping.com/mlogin/dp/api/v1/qrlogin/check"
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
}


def _ordered_params(**values: Any) -> list[tuple[str, str]]:
    """Build an ordered query list without allowing dict reordering drift."""
    return [(name, str(value)) for name, value in values.items()]


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
        # The last wire contract is intentionally metadata only.  It is useful
        # when comparing a replay with DevTools while keeping cookies, H5guard
        # values, fingerprints and QR material out of logs.
        self.last_contract: dict[str, Any] = {}
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
        response = self.session.request(method, url, headers=headers, **kwargs)
        params = kwargs.get("params")
        if isinstance(params, Mapping):
            param_names = list(params.keys())
        elif isinstance(params, (list, tuple)):
            param_names = [str(item[0]) for item in params if isinstance(item, (list, tuple)) and item]
        else:
            param_names = []
        self.last_contract = {
            "method": method.upper(),
            "url": url,
            "param_names": param_names,
            "header_names": sorted(str(name).lower() for name in headers),
            "status": int(getattr(response, "status_code", getattr(response, "status", 0)) or 0),
        }
        return response

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
        raw = getattr(response, "content", b"")
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        text = getattr(response, "text", None)
        return text if isinstance(text, str) else str(raw)

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

    def bootstrap_guest(
        self,
        *,
        h5_fingerprint: str | None = None,
        mtgsig: str | None = None,
        yoda_ready: str = "h5",
        csec_platform: int = 4,
        csec_version: str = "4.3.0",
    ) -> Mapping[str, Any]:
        """Create the anonymous login-page session observed in Chrome.

        The first two requests are public cache-token reads.  The login page
        then sends ``checkLogin`` only after its H5guard runtime has produced
        a current fingerprint and signature.  Those values are deliberately
        caller supplied; this method never invents them or executes a browser
        challenge.  The return value contains response metadata and the
        server's JSON status, never the raw dynamic values.
        """
        common_headers = {
            "Accept": "*/*",
            "Origin": ACCOUNT_ORIGIN,
            "Referer": ACCOUNT_REFERER,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        }
        cache_results: dict[str, Any] = {}
        for name, url in (("cache_token", CACHE_TOKEN_URL), ("cache_token_p", CACHE_TOKEN_P_URL)):
            response = self.request("GET", url, headers=common_headers)
            status = int(getattr(response, "status_code", 0) or 0)
            if status not in range(200, 300):
                if self._is_challenge_response(response):
                    raise AccessRequired("Dianping guest bootstrap reached an interactive verification")
                raise DianpingError(f"Dianping guest bootstrap {name} returned HTTP {status}")
            cache_results[name] = {
                "status": status,
                "content_type": str((getattr(response, "headers", {}) or {}).get("content-type", "")),
                "length": len(getattr(response, "content", b"") or b""),
            }

        result: dict[str, Any] = {"cache": cache_results}
        if h5_fingerprint is None and mtgsig is None:
            result["check_login"] = {"skipped": True, "reason": "h5guard_values_not_supplied"}
            return result
        if not h5_fingerprint or not mtgsig:
            raise ValueError("h5_fingerprint and mtgsig must be supplied together")

        # DevTools shows the signature in the query string for this POST.  It
        # is not the same placement as the QR image/check requests, which use
        # an mtgsig request header.
        params = _ordered_params(
            yodaReady=yoda_ready,
            csecplatform=csec_platform,
            csecversion=csec_version,
            mtgsig=mtgsig,
        )
        response = self.request(
            "POST",
            CHECK_LOGIN_URL,
            params=params,
            data=b"",
            headers={
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": ACCOUNT_ORIGIN,
                "Referer": f"{LOGIN_PAGE_URL}/",
                "X-Requested-With": "XMLHttpRequest",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
            },
        )
        status = int(getattr(response, "status_code", 0) or 0)
        if status != 200:
            if self._is_challenge_response(response):
                raise AccessRequired("Dianping checkLogin reached an interactive verification")
            raise DianpingError(f"Dianping checkLogin returned HTTP {status}")
        try:
            check_data = response.json()
        except (AttributeError, ValueError):
            check_data = {"raw": self._response_text(response)[:160]}
        result["check_login"] = check_data if isinstance(check_data, Mapping) else {"value": check_data}
        return result

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
        # Keep this sequence identical to the observed browser URL.  A plain
        # dict currently preserves insertion order on CPython, but a tuple
        # list makes that contract explicit for alternate clients/tests.
        params = _ordered_params(
            risk_app=risk_app,
            risk_partner=risk_partner,
            risk_platform=risk_platform,
            h5_fingerprint=h5_fingerprint,
            yodaReady=yoda_ready,
            csecplatform=csec_platform,
            csecversion=csec_version,
        )
        response = self.request(
            "GET",
            QR_IMAGE_URL,
            params=params,
            headers={
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Origin": ACCOUNT_ORIGIN,
                "Referer": ACCOUNT_REFERER,
                "Sec-Fetch-Dest": "image",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "mtgsig": mtgsig,
            },
        )
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
        yoda_ready: str = "h5",
        csec_platform: int = 4,
        csec_version: str = "4.3.0",
        interval: float = 2.0,
        timeout: float = 180.0,
    ) -> Mapping[str, Any]:
        """Poll after the user scans in the official Dianping app."""
        if not h5_fingerprint.strip():
            raise ValueError("h5_fingerprint is required")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            signature = mtgsig(challenge.qruuid) if callable(mtgsig) else mtgsig
            if not signature or not str(signature).strip():
                raise ValueError("mtgsig callback returned an empty signature")
            params = _ordered_params(
                qruuid=challenge.qruuid,
                risk_app=risk_app,
                risk_partner=risk_partner,
                risk_platform=risk_platform,
                h5_fingerprint=h5_fingerprint,
                yodaReady=yoda_ready,
                csecplatform=csec_platform,
                csecversion=csec_version,
            )
            response = self.request(
                "GET",
                challenge.check_url,
                params=params,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Origin": ACCOUNT_ORIGIN,
                    "Referer": ACCOUNT_REFERER,
                    "Sec-Fetch-Dest": "empty",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Site": "same-site",
                    "mtgsig": str(signature),
                },
            )
            status = int(getattr(response, "status_code", 0) or 0)
            if status != 200:
                raise AccessRequired("Dianping QR status request was rejected")
            try:
                data = response.json()
            except (AttributeError, ValueError) as exc:
                raise DianpingError("Dianping QR status was not JSON") from exc
            if not isinstance(data, Mapping):
                raise DianpingError("Dianping QR status had an unexpected shape")
            inner = data.get("data")
            nested_status = inner.get("status") if isinstance(inner, Mapping) else None
            state = str(nested_status if nested_status is not None else data.get("status", data.get("code", data.get("errno", "")))).lower()
            description = str(inner.get("description", "") if isinstance(inner, Mapping) else data.get("description", ""))
            pending_description = any(marker in description for marker in ("未扫描", "等待", "二维码"))
            if state not in {"", "0", "200", "pending", "wait", "waiting", "1"} or (state == "200" and not pending_description):
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

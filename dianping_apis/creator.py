"""Dianping note and shop-review browser workflows.

These are browser controls, not undocumented HTTP endpoints.  Logged-in site
layout may vary by account; missing controls fail explicitly.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Iterable
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .auth import DianpingAuth, NOTE_URL
from .client import _validate_item_url
from .errors import AccessRequired, ElementMissing, SubmissionUnconfirmed
from .models import SubmissionResult

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page


class DianpingCreatorAPI:
    """Compose and submit the account owner's original content."""

    def __init__(self, auth_or_page: DianpingAuth | "Page"):
        self.page = auth_or_page.require_page() if isinstance(auth_or_page, DianpingAuth) else auth_or_page

    def _check_login(self) -> None:
        host = urlparse(self.page.url).hostname
        if host in {"account.dianping.com", "verify.meituan.com"}:
            raise AccessRequired("Complete Dianping login or interactive verification in the browser")

    def _visible(self, selectors: Iterable[str]) -> "Locator":
        # CSS :visible works with the project's Playwright >=1.50 floor.  A
        # locator waits for async controls and skips hidden duplicate forms.
        locator = self.page.locator(", ".join(f"{selector}:visible" for selector in selectors)).first
        try:
            locator.wait_for(state="visible", timeout=5_000)
        except PlaywrightTimeoutError as exc:
            self._check_login()
            raise ElementMissing("Expected publishing form control is absent from this account's page") from exc
        return locator

    def _fill(self, selectors: Iterable[str], value: str) -> None:
        self._visible(selectors).fill(value)

    def _upload(self, images: Iterable[str | Path]) -> None:
        paths = [str(Path(path).expanduser().resolve()) for path in images]
        for path in paths:
            if not Path(path).is_file():
                raise FileNotFoundError(path)
        if paths:
            upload = self.page.locator('input[type="file"]').first
            if not upload.count():
                raise ElementMissing("The publishing page does not have a media upload control")
            upload.set_input_files(paths)

    def _submit(self, kind: str) -> SubmissionResult:
        confirmation = self.page.locator(
            ':text-matches("发布成功|发表成功|提交成功"):visible'
        ).first
        if confirmation.is_visible():
            raise SubmissionUnconfirmed("A success message was already visible before submit")
        self._visible(
            ('button:has-text("发布")', 'button:has-text("发表")',
             'button:has-text("提交")', '[role="button"]:has-text("发布")')
        ).click()
        self._check_login()
        # A URL containing /review/ can be an ordinary review list.  Only a
        # visible confirmation is strong enough to report a successful write.
        try:
            confirmation.wait_for(state="visible", timeout=5_000)
        except PlaywrightTimeoutError as exc:
            self._check_login()
            raise SubmissionUnconfirmed(
                "Clicked submit but no visible success message appeared; check the account manually"
            ) from exc
        return SubmissionResult(kind, self.page.url, "visible success message")

    def publish_note(
        self,
        title: str,
        content: str,
        *,
        images: Iterable[str | Path] = (),
        shop_name: str | None = None,
        submit: bool = False,
    ) -> SubmissionResult:
        """Fill the verified `/note/create` page and optionally submit it."""
        if not title.strip() or not content.strip():
            raise ValueError("title and content are required")
        self.page.goto(NOTE_URL, wait_until="domcontentloaded")
        self._check_login()
        if urlparse(self.page.url).hostname != "www.dianping.com" or urlparse(self.page.url).path != "/note/create":
            raise ElementMissing("The browser did not reach Dianping's note editor")
        self._fill(('input[placeholder*="标题"]', 'textarea[placeholder*="标题"]', 'input[name="title"]'), title)
        self._fill(
            ('[contenteditable="true"]', 'textarea[placeholder*="正文"]',
             'textarea[placeholder*="内容"]', 'textarea[name="content"]'),
            content,
        )
        self._upload(images)
        if shop_name:
            self._fill(('input[placeholder*="商户"]', 'input[placeholder*="店铺"]'), shop_name)
            # Limit this click to an actual option. Arbitrary matching text may
            # refer to a heading elsewhere on the page.
            suggestion = self.page.get_by_role("option", name=shop_name, exact=True).first
            try:
                suggestion.wait_for(state="visible", timeout=5_000)
            except PlaywrightTimeoutError as exc:
                raise ElementMissing("Shop suggestion did not appear; choose the shop in the browser") from exc
            suggestion.click()
        draft_url = self.page.url
        return self._submit("note") if submit else SubmissionResult("note", draft_url, "form filled; not submitted")

    def publish_review(
        self,
        shop_url: str,
        content: str,
        *,
        rating: int,
        images: Iterable[str | Path] = (),
        submit: bool = False,
    ) -> SubmissionResult:
        """Open a shop's visible 写点评 form, then submit original content."""
        kind, _shop_id = _validate_item_url(shop_url)
        if kind != "shop":
            raise ValueError("shop_url must point to a Dianping shop")
        if not content.strip():
            raise ValueError("content is required")
        if type(rating) is not int or rating not in range(1, 6):
            raise ValueError("rating must be an integer from 1 to 5")
        self.page.goto(shop_url, wait_until="domcontentloaded")
        self._check_login()
        self._visible(
            ('a:has-text("写点评")', 'button:has-text("写点评")',
             '[role="button"]:has-text("写点评")')
        ).click()
        self._check_login()
        self._fill(
            ('textarea[placeholder*="点评"]', 'textarea[placeholder*="评价"]',
             '[contenteditable="true"]', 'textarea'),
            content,
        )
        self._visible(
            (f'[aria-label="{rating}星"]', f'[aria-label*="{rating}星"]',
             f'[title="{rating}星"]', f'button:has-text("{rating}星")')
        ).click()
        self._upload(images)
        draft_url = self.page.url
        return self._submit("review") if submit else SubmissionResult("review", draft_url, "form filled; not submitted")

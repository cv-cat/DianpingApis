"""Consumer publishing contracts awaiting a verified platform entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .auth import DianpingAuth
from .client import _validate_item_url
from .errors import PublishingUnavailable
from .models import SubmissionResult

class DianpingCreatorAPI:
    """Explicit publishing API boundary for the account owner's content.

    The authenticated consumer Web pages inspected on 2026-10-07 have no
    usable note or review editor. Do not navigate to `/note/create`: the site
    treats `create` as a note ID, not an editor route.
    """

    def __init__(self, auth_or_page: DianpingAuth):
        self.auth_or_page = auth_or_page

    def publish_note(
        self,
        title: str,
        content: str,
        *,
        images: Iterable[str | Path] = (),
        shop_name: str | None = None,
        submit: bool = False,
    ) -> SubmissionResult:
        """Report the current lack of a verified Web note publishing flow."""
        if not title.strip() or not content.strip():
            raise ValueError("title and content are required")
        raise PublishingUnavailable(
            "Dianping's consumer Web page has no verified note editor; "
            "publishing needs a separately verified App flow"
        )

    def publish_review(
        self,
        shop_url: str,
        content: str,
        *,
        rating: int,
        images: Iterable[str | Path] = (),
        submit: bool = False,
    ) -> SubmissionResult:
        """Report the current lack of a verified Web shop-review form."""
        kind, _shop_id = _validate_item_url(shop_url)
        if kind != "shop":
            raise ValueError("shop_url must point to a Dianping shop")
        if not content.strip():
            raise ValueError("content is required")
        if type(rating) is not int or rating not in range(1, 6):
            raise ValueError("rating must be an integer from 1 to 5")
        raise PublishingUnavailable(
            "Dianping's consumer Web shop pages have no verified review form; "
            "publishing needs a separately verified App flow"
        )
